package app.locallink.mobile;

import android.content.Context;
import android.content.res.AssetManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class MobileHostServer {
    static final int PORT = 53317;
    private final Context context;
    private final String deviceName;
    private final String pairingCode;
    private final File root;
    private final File filesDir;
    private final File historyFile;
    private final Object storeLock = new Object();
    private final ArrayList<JSONObject> records = new ArrayList<>();
    private final ExecutorService clients = Executors.newCachedThreadPool();
    private final PairingThrottle throttle = new PairingThrottle();
    private volatile boolean running;
    private ServerSocket socket;

    MobileHostServer(Context context, String deviceName, String pairingCode) {
        this.context = context.getApplicationContext();
        this.deviceName = deviceName;
        this.pairingCode = pairingCode;
        root = new File(context.getFilesDir(), "LocalLinkData");
        filesDir = new File(root, "files");
        historyFile = new File(root, "history.json");
        filesDir.mkdirs();
        loadHistory();
    }

    void start() throws Exception {
        socket = new ServerSocket(PORT);
        socket.setReuseAddress(true);
        running = true;
        Thread accept = new Thread(() -> {
            while (running) {
                try { Socket accepted = socket.accept(); clients.execute(() -> handle(accepted)); }
                catch (Exception error) { if (running) error.printStackTrace(); }
            }
        }, "locallink-mobile-http");
        accept.setDaemon(true); accept.start();
    }

    void stop() {
        running = false;
        try { if (socket != null) socket.close(); } catch (Exception ignored) {}
        clients.shutdownNow();
    }

    boolean isRunning() { return running; }

    private void handle(Socket client) {
        try (Socket closeable = client;
             BufferedInputStream in = new BufferedInputStream(closeable.getInputStream());
             BufferedOutputStream out = new BufferedOutputStream(closeable.getOutputStream())) {
            closeable.setSoTimeout(30000);
            String requestLine = readLine(in);
            if (requestLine == null || requestLine.isEmpty()) return;
            String[] parts = requestLine.split(" ", 3);
            if (parts.length < 2) { sendText(out, 400, "Bad Request", "text/plain", "bad request".getBytes()); return; }
            String method = parts[0], target = parts[1];
            HashMap<String,String> headers = new HashMap<>();
            String line;
            while ((line = readLine(in)) != null && !line.isEmpty()) {
                int split = line.indexOf(':');
                if (split > 0) headers.put(line.substring(0, split).trim().toLowerCase(Locale.ROOT), line.substring(split + 1).trim());
            }
            String path = target.split("\\?", 2)[0];
            if (path.equals("/api/health")) { sendJson(out, 200, health()); return; }
            if (path.equals("/") || path.equals("/index.html")) { sendAsset(out, "index.html"); return; }
            if (path.startsWith("/static/")) { sendAsset(out, path.substring(8)); return; }
            // Refuse before comparing: a throttled source must not keep trying
            // codes just because it is willing to sit through the backoff.
            String source = closeable.getInetAddress() == null ? "" : closeable.getInetAddress().getHostAddress();
            throttle.waitOut(source);
            int cooldown = throttle.retryAfter(source);
            if (cooldown > 0) {
                throttle.record(source, false);
                sendText(out, 429, "Too Many Requests", "application/json; charset=utf-8",
                        new JSONObject().put("ok", false).put("error", "配对尝试过于频繁，请稍后重试")
                                .toString().getBytes(StandardCharsets.UTF_8),
                        Collections.singletonMap("Retry-After", String.valueOf(cooldown)));
                return;
            }
            boolean allowed = authorized(target, headers);
            throttle.record(source, allowed);
            if (!allowed) { sendError(out, 401, "配对码错误"); return; }
            if (method.equals("GET") && path.equals("/api/status")) { sendJson(out, 200, status()); return; }
            if (method.equals("POST") && path.equals("/api/scan")) { LocalLinkService.scanSubnet(); sendJson(out, 202, new JSONObject().put("ok", true).put("started", true)); return; }
            if (method.equals("POST") && path.equals("/api/text")) { addText(out, in, headers); return; }
            if (method.equals("POST") && path.equals("/api/upload")) { addFile(out, in, headers); return; }
            if (method.equals("GET") && path.startsWith("/api/download/")) { download(out, path.substring(path.lastIndexOf('/') + 1), headers); return; }
            if (method.equals("GET") && path.startsWith("/api/preview/")) { download(out, path.substring(path.lastIndexOf('/') + 1), headers, true); return; }
            if (method.equals("DELETE") && path.equals("/api/items")) { clear(out); return; }
            if (method.equals("DELETE") && path.startsWith("/api/items/")) { delete(out, path.substring(path.lastIndexOf('/') + 1)); return; }
            sendError(out, 404, "未找到");
        } catch (Exception ignored) {}
    }

    JSONObject health() throws Exception {
        return new JSONObject().put("ok", true).put("service", "locallink").put("version", "2")
            .put("id", LocalLinkService.deviceId()).put("name", deviceName).put("port", PORT);
    }

    private JSONObject status() throws Exception {
        String ip = LocalLinkService.wifiAddress();
        JSONArray history = historyJson();
        int fileCount = 0; long bytes = 0;
        synchronized (storeLock) {
            for (JSONObject item : records) if ("file".equals(item.optString("kind"))) {
                File file = fileFor(item); if (file.isFile()) { fileCount++; bytes += file.length(); }
            }
        }
        return new JSONObject().put("ok", true).put("device", deviceName).put("ip", ip).put("port", PORT)
            .put("pairing_code", pairingCode).put("device_id", LocalLinkService.deviceId()).put("share_url", "http://" + ip + ":" + PORT + "/?code=" + pairingCode)
            .put("network", new JSONObject().put("vpn_detected", false).put("lan_state", "ok").put("firewall", "not_required").put("message", "Android 本机收件箱正在运行"))
            .put("peers", LocalLinkService.peersJson()).put("auth", throttle.snapshot()).put("storage", new JSONObject().put("items", history.length()).put("files", fileCount).put("bytes", bytes).put("bytes_human", humanSize(bytes)))
            .put("history", history);
    }

    private void addText(BufferedOutputStream out, InputStream in, Map<String,String> headers) throws Exception {
        byte[] body = readBody(in, contentLength(headers), 300000);
        JSONObject request = new JSONObject(new String(body, StandardCharsets.UTF_8));
        String text = request.optString("text", "");
        if (text.trim().isEmpty()) { sendError(out, 400, "不能发送空文本"); return; }
        byte[] encoded = text.getBytes(StandardCharsets.UTF_8);
        JSONObject item = baseRecord("text", "文本消息", encoded.length, sha256(encoded), request.optString("sender", "手机端"));
        item.put("text", text);
        saveRecord(item); LocalLinkService.notifyReceived("收到文字", request.optString("sender", "其他设备") + " 发来一条文字消息"); sendJson(out, 201, new JSONObject().put("ok", true).put("item", item));
    }

    private void addFile(BufferedOutputStream out, InputStream in, Map<String,String> headers) throws Exception {
        long length = contentLength(headers);
        if (length < 0) { sendError(out, 400, "文件大小无效"); return; }
        String name = safeName(decode(headers.getOrDefault("x-filename", "unnamed-file")));
        String id = UUID.randomUUID().toString().replace("-", "");
        File part = new File(filesDir, id + "--" + name + ".part");
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long remaining = length;
        try (FileOutputStream target = new FileOutputStream(part)) {
            byte[] buffer = new byte[1024 * 1024];
            while (remaining > 0) { int read = in.read(buffer, 0, (int)Math.min(buffer.length, remaining)); if (read < 0) break; target.write(buffer, 0, read); digest.update(buffer, 0, read); remaining -= read; }
        }
        if (remaining != 0) { part.delete(); sendError(out, 400, "文件接收不完整"); return; }
        String actual = hex(digest.digest());
        String expected = headers.getOrDefault("x-sha256", "");
        if (!expected.isEmpty() && !actual.equalsIgnoreCase(expected)) { part.delete(); sendError(out, 400, "SHA-256 校验失败"); return; }
        File finalFile = new File(filesDir, id + "--" + name);
        if (!part.renameTo(finalFile)) { part.delete(); sendError(out, 500, "文件保存失败"); return; }
        JSONObject item = baseRecord("file", name, length, actual, decode(headers.getOrDefault("x-sender", "手机端"))); item.put("id", id);
        saveRecord(item); LocalLinkService.notifyReceived("收到文件", name + " · " + humanSize(length)); sendJson(out, 201, new JSONObject().put("ok", true).put("item", item));
    }

    private void download(BufferedOutputStream out, String id, Map<String,String> headers) throws Exception {
        download(out,id,headers,false);
    }

    private void download(BufferedOutputStream out, String id, Map<String,String> headers, boolean inline) throws Exception {
        JSONObject item = find(id);
        if (item == null || !"file".equals(item.optString("kind"))) { sendError(out, 404, "文件不存在"); return; }
        File file = fileFor(item); if (!file.isFile()) { sendError(out, 410, "文件已移除"); return; }
        long total = file.length(), start = 0, end = total - 1; int status = 200;
        String range = headers.getOrDefault("range", "");
        if (range.startsWith("bytes=")) { try { String[] values=range.substring(6).split("-",2); start=Long.parseLong(values[0]); if(values.length>1&&!values[1].isEmpty())end=Long.parseLong(values[1]); status=206; } catch(Exception ignored){} }
        long length=end-start+1;
        HashMap<String,String> extra=new HashMap<>(); extra.put("Content-Disposition", (inline?"inline":"attachment")+"; filename*=UTF-8''"+java.net.URLEncoder.encode(item.optString("name"), "UTF-8").replace("+", "%20")); extra.put("Accept-Ranges","bytes"); if(status==206)extra.put("Content-Range","bytes "+start+"-"+end+"/"+total);
        sendHeaders(out,status,status==206?"Partial Content":"OK",mime(item.optString("name")),length,extra);
        try(FileInputStream source=new FileInputStream(file)){source.skip(start);byte[] buffer=new byte[1024*1024];long remaining=length;while(remaining>0){int read=source.read(buffer,0,(int)Math.min(buffer.length,remaining));if(read<0)break;out.write(buffer,0,read);remaining-=read;}} out.flush();
    }

    private void delete(BufferedOutputStream out, String id) throws Exception {
        boolean deleted=false; synchronized(storeLock){Iterator<JSONObject> iterator=records.iterator();while(iterator.hasNext()){JSONObject item=iterator.next();if(id.equals(item.optString("id"))){if("file".equals(item.optString("kind")))fileFor(item).delete();iterator.remove();deleted=true;break;}}if(deleted)persist();}
        sendJson(out,deleted?200:404,new JSONObject().put("ok",deleted));
    }

    private void clear(BufferedOutputStream out) throws Exception {
        int count; synchronized(storeLock){count=records.size();for(JSONObject item:records)if("file".equals(item.optString("kind")))fileFor(item).delete();records.clear();persist();}
        sendJson(out,200,new JSONObject().put("ok",true).put("deleted",count));
    }

    private JSONObject baseRecord(String kind,String name,long size,String hash,String sender)throws Exception{return new JSONObject().put("id",UUID.randomUUID().toString().replace("-","")).put("kind",kind).put("name",name).put("size",size).put("sha256",hash).put("created_at",System.currentTimeMillis()/1000.0).put("sender",sender).put("receiver",deviceName).put("text","");}
    private void saveRecord(JSONObject item)throws Exception{synchronized(storeLock){records.add(item);persist();}}
    private JSONObject find(String id){synchronized(storeLock){for(JSONObject item:records)if(id.equals(item.optString("id")))return item;}return null;}
    private File fileFor(JSONObject item){return new File(filesDir,item.optString("id")+"--"+item.optString("name"));}
    File recordFile(String id){JSONObject item=find(id);if(item==null||!"file".equals(item.optString("kind")))return null;File file=fileFor(item);try{File root=filesDir.getCanonicalFile(),candidate=file.getCanonicalFile();return candidate.toPath().startsWith(root.toPath())&&candidate.isFile()?candidate:null;}catch(Exception ignored){return null;}}
    private JSONArray historyJson()throws Exception{JSONArray result=new JSONArray();synchronized(storeLock){for(int i=records.size()-1;i>=0;i--){JSONObject original=records.get(i);JSONObject item=new JSONObject(original.toString());item.put("size_human",humanSize(item.optLong("size")));item.put("available",!"file".equals(item.optString("kind"))||fileFor(item).isFile());if("text".equals(item.optString("kind"))){item.put("mime_type","text/plain; charset=utf-8").put("category","text").put("actions",new JSONArray().put("preview_inline")).put("installable",false);}else{FileCapabilities.Result capability=FileCapabilities.resolve(item.optString("name"),FileCapabilities.mimeFor(item.optString("name")));item.put("mime_type",capability.mimeType).put("category",capability.category).put("actions",new JSONArray(capability.actions)).put("installable",capability.installable);}result.put(item);}}return result;}
    private void loadHistory(){synchronized(storeLock){try{if(!historyFile.isFile())return;byte[] data=new byte[(int)historyFile.length()];try(FileInputStream in=new FileInputStream(historyFile)){int ignored=in.read(data);}JSONArray array=new JSONArray(new String(data,StandardCharsets.UTF_8));for(int i=0;i<array.length();i++)records.add(array.getJSONObject(i));}catch(Exception ignored){records.clear();}}}
    private void persist()throws Exception{root.mkdirs();try(FileOutputStream out=new FileOutputStream(historyFile)){out.write(new JSONArray(records).toString(2).getBytes(StandardCharsets.UTF_8));}}
    private boolean authorized(String target,Map<String,String> headers){String supplied=headers.getOrDefault("x-locallink-code","");int query=target.indexOf('?');if(supplied.isEmpty()&&query>=0){for(String part:target.substring(query+1).split("&")){String[] kv=part.split("=",2);if(kv.length==2&&kv[0].equals("code"))supplied=decode(kv[1]);}}return pairingCode.equals(supplied);}
    static boolean isBundledAsset(String name){
        if(name==null||!name.matches("[A-Za-z0-9._-]+"))return false;
        String lower=name.toLowerCase(Locale.ROOT);
        return lower.endsWith(".html")||lower.endsWith(".css")||lower.endsWith(".js")||lower.endsWith(".png")||lower.endsWith(".svg")||lower.endsWith(".ico");
    }
    private void sendAsset(BufferedOutputStream out,String name)throws Exception{if(!isBundledAsset(name)){sendError(out,404,"未找到");return;}AssetManager assets=context.getAssets();try(InputStream in=assets.open(name);ByteArrayOutputStream data=new ByteArrayOutputStream()){byte[] buffer=new byte[16384];int read;while((read=in.read(buffer))>=0)data.write(buffer,0,read);sendText(out,200,"OK",mime(name),data.toByteArray());}}
    private void sendJson(BufferedOutputStream out,int status,JSONObject json)throws Exception{sendText(out,status,status<300?"OK":"Error","application/json; charset=utf-8",json.toString().getBytes(StandardCharsets.UTF_8));}
    private void sendError(BufferedOutputStream out,int status,String message)throws Exception{sendJson(out,status,new JSONObject().put("ok",false).put("error",message));}
    private void sendText(BufferedOutputStream out,int status,String reason,String type,byte[] body)throws Exception{sendText(out,status,reason,type,body,Collections.emptyMap());}
    private void sendText(BufferedOutputStream out,int status,String reason,String type,byte[] body,Map<String,String> extra)throws Exception{sendHeaders(out,status,reason,type,body.length,extra);out.write(body);out.flush();}
    private void sendHeaders(BufferedOutputStream out,int status,String reason,String type,long length,Map<String,String> extra)throws Exception{StringBuilder value=new StringBuilder("HTTP/1.1 ").append(status).append(' ').append(reason).append("\r\nContent-Type: ").append(type).append("\r\nContent-Length: ").append(length).append("\r\nCache-Control: no-store\r\nConnection: close\r\n");for(Map.Entry<String,String> item:extra.entrySet())value.append(item.getKey()).append(": ").append(item.getValue()).append("\r\n");value.append("\r\n");out.write(value.toString().getBytes(StandardCharsets.ISO_8859_1));}
    private static String readLine(InputStream in)throws Exception{ByteArrayOutputStream data=new ByteArrayOutputStream();int previous=-1,current;while((current=in.read())>=0){if(previous=='\r'&&current=='\n'){byte[] raw=data.toByteArray();return new String(raw,0,Math.max(0,raw.length-1),StandardCharsets.ISO_8859_1);}data.write(current);previous=current;if(data.size()>16384)throw new IllegalArgumentException("header too large");}return data.size()==0?null:data.toString("ISO-8859-1");}
    private static long contentLength(Map<String,String> headers){try{return Long.parseLong(headers.getOrDefault("content-length","-1"));}catch(Exception error){return -1;}}
    private static byte[] readBody(InputStream in,long length,long max)throws Exception{if(length<0||length>max)throw new IllegalArgumentException("body size");byte[] data=new byte[(int)length];int offset=0;while(offset<data.length){int read=in.read(data,offset,data.length-offset);if(read<0)break;offset+=read;}if(offset!=data.length)throw new IllegalArgumentException("incomplete body");return data;}
    private static String safeName(String value){String name=new File(value.replace('\\','/')).getName().replaceAll("[<>:\"/\\\\|?*\\x00-\\x1f]","_").replaceAll("^[. ]+|[. ]+$","");return name.isEmpty()?"unnamed-file":name.substring(0,Math.min(180,name.length()));}
    private static String decode(String value){try{return URLDecoder.decode(value,"UTF-8");}catch(Exception error){return value;}}
    private static String sha256(byte[] data)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(data));}
    private static String hex(byte[] data){StringBuilder out=new StringBuilder();for(byte value:data)out.append(String.format(Locale.ROOT,"%02x",value));return out.toString();}
    private static String humanSize(long size){double value=size;String[] units={"B","KB","MB","GB"};for(String unit:units){if(value<1024||unit.equals("GB"))return unit.equals("B")?String.format(Locale.ROOT,"%.0f %s",value,unit):String.format(Locale.ROOT,"%.1f %s",value,unit);value/=1024;}return size+" B";}
    private static String mime(String name){String lower=name.toLowerCase(Locale.ROOT);if(lower.endsWith(".html"))return "text/html; charset=utf-8";if(lower.endsWith(".css"))return "text/css; charset=utf-8";if(lower.endsWith(".js"))return "application/javascript; charset=utf-8";if(lower.endsWith(".png"))return "image/png";if(lower.endsWith(".jpg")||lower.endsWith(".jpeg"))return "image/jpeg";if(lower.endsWith(".pdf"))return "application/pdf";if(lower.endsWith(".txt"))return "text/plain; charset=utf-8";return "application/octet-stream";}
}
