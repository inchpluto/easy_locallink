package app.locallink.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ClipData;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.AssetFileDescriptor;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST=801;
    private static final int NOTIFICATION_REQUEST=802;
    private static final int INK=Color.rgb(22,24,29),MUTED=Color.rgb(105,112,125),LINE=Color.rgb(226,229,233),BLUE=Color.rgb(37,99,235),GREEN=Color.rgb(32,164,100),SOFT=Color.rgb(246,247,249);
    private SharedPreferences preferences;
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private LinearLayout peersContainer;
    private TextView hostStatus;
    private final ArrayList<Uri> pendingUris=new ArrayList<>();
    private String pendingText="";
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable peerRefresh=new Runnable(){@Override public void run(){if(peersContainer!=null)renderPeers();handler.postDelayed(this,3000);}};

    @Override public void onCreate(Bundle state){
        super.onCreate(state);preferences=getSharedPreferences("locallink",MODE_PRIVATE);parseShareIntent(getIntent());
        Window window=getWindow();window.setStatusBarColor(Color.WHITE);window.setNavigationBarColor(Color.WHITE);window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        bindToWifi();
        Intent service=new Intent(this,LocalLinkService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(service);else startService(service);
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFICATION_REQUEST);
        showDeviceScreen();
    }

    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);parseShareIntent(intent);showDeviceScreen();}

    private void parseShareIntent(Intent intent){pendingUris.clear();pendingText="";if(intent==null)return;String action=intent.getAction();if(!Intent.ACTION_SEND.equals(action)&&!Intent.ACTION_SEND_MULTIPLE.equals(action))return;CharSequence text=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);if(text!=null)pendingText=text.toString();if(Intent.ACTION_SEND_MULTIPLE.equals(action)){ArrayList<Uri> values=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(values!=null)pendingUris.addAll(values);}else{Uri value=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(value!=null)pendingUris.add(value);}ClipData clip=intent.getClipData();if(clip!=null)for(int i=0;i<clip.getItemCount();i++){Uri value=clip.getItemAt(i).getUri();if(value!=null&&!pendingUris.contains(value))pendingUris.add(value);}}
    private boolean hasPendingShare(){return !pendingText.trim().isEmpty()||!pendingUris.isEmpty();}

    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private LinearLayout.LayoutParams match(int height){return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,height);}
    private GradientDrawable shape(int fill,int stroke,int radius){GradientDrawable value=new GradientDrawable();value.setColor(fill);value.setCornerRadius(dp(radius));if(stroke!=Color.TRANSPARENT)value.setStroke(dp(1),stroke);return value;}
    private TextView text(String value,int size,int color){TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(color);return view;}
    private TextView label(String value){TextView view=text(value,12,MUTED);view.setTypeface(null,Typeface.BOLD);return view;}
    private Button button(String value,boolean primary){Button view=new Button(this);view.setText(value);view.setAllCaps(false);view.setTextSize(14);view.setTypeface(null,Typeface.BOLD);view.setTextColor(primary?Color.WHITE:INK);view.setBackground(shape(primary?BLUE:Color.WHITE,primary?Color.TRANSPARENT:LINE,10));return view;}
    private EditText input(String value,boolean numeric){EditText view=new EditText(this);view.setSingleLine(true);view.setText(value);view.setTextColor(INK);view.setTextSize(16);view.setPadding(dp(14),0,dp(14),0);view.setBackground(shape(Color.WHITE,LINE,10));if(numeric)view.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);return view;}
    private LinearLayout card(){LinearLayout value=new LinearLayout(this);value.setOrientation(LinearLayout.VERTICAL);value.setPadding(dp(18),dp(19),dp(18),dp(19));value.setBackground(shape(Color.WHITE,LINE,16));return value;}

    private void showDeviceScreen(){
        if(webView!=null){webView.destroy();webView=null;} peersContainer=null;handler.removeCallbacks(peerRefresh);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(SOFT);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(18),dp(24),dp(18),dp(36));scroll.addView(root,new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView brand=text("LOCAL/LINK",17,INK);brand.setTypeface(null,Typeface.BOLD);brand.setLetterSpacing(.08f);root.addView(brand,match(dp(48)));
        TextView kicker=text("同一局域网 · 无需互联网",11,BLUE);kicker.setTypeface(null,Typeface.BOLD);kicker.setLetterSpacing(.08f);LinearLayout.LayoutParams kp=match(dp(28));kp.topMargin=dp(6);root.addView(kicker,kp);
        TextView title=text("连接本地设备",30,INK);title.setTypeface(null,Typeface.BOLD);root.addView(title,match(dp(58)));
        if(hasPendingShare()){TextView pending=text("待发送 · "+(!pendingText.trim().isEmpty()?"文字 ":"")+(pendingUris.isEmpty()?"":pendingUris.size()+" 个文件")+"\n请选择下方接收设备",14,BLUE);pending.setTypeface(null,Typeface.BOLD);pending.setPadding(dp(16),dp(12),dp(16),dp(12));pending.setBackground(shape(Color.rgb(237,243,255),Color.rgb(199,215,255),12));LinearLayout.LayoutParams pp=match(dp(68));pp.bottomMargin=dp(14);root.addView(pending,pp);}

        LinearLayout own=card();root.addView(own,match(ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView ownTitle=text("我的本机收件箱",20,INK);ownTitle.setTypeface(null,Typeface.BOLD);own.addView(ownTitle,match(dp(36)));
        String ownIp=LocalLinkService.wifiAddress();String localCode=preferences.getString("local_code","123456");
        hostStatus=text((LocalLinkService.isHostRunning()?"● 服务在线":"● 服务启动中")+"\n"+ownIp+":"+MobileHostServer.PORT+"  ·  配对码 "+localCode,13,LocalLinkService.isHostRunning()?GREEN:MUTED);hostStatus.setLineSpacing(0,1.45f);own.addView(hostStatus,match(dp(58)));
        Button openOwn=button("打开本机收件箱",true);LinearLayout.LayoutParams op=match(dp(50));op.topMargin=dp(12);own.addView(openOwn,op);openOwn.setOnClickListener(v->openLocalInbox());

        addTrustedDevices(root);

        LinearLayout sectionHead=new LinearLayout(this);sectionHead.setGravity(Gravity.CENTER_VERTICAL);LinearLayout.LayoutParams shp=match(dp(68));shp.topMargin=dp(20);root.addView(sectionHead,shp);
        TextView nearby=text("附近的 LocalLink 设备",18,INK);nearby.setTypeface(null,Typeface.BOLD);sectionHead.addView(nearby,new LinearLayout.LayoutParams(0,dp(58),1));
        Button scan=button("扫描",false);sectionHead.addView(scan,new LinearLayout.LayoutParams(dp(88),dp(44)));scan.setOnClickListener(v->{scan.setEnabled(false);LocalLinkService.scanSubnet();toast("正在扫描当前 Wi-Fi 网段");handler.postDelayed(()->{scan.setEnabled(true);renderPeers();},1800);});
        peersContainer=new LinearLayout(this);peersContainer.setOrientation(LinearLayout.VERTICAL);root.addView(peersContainer,match(ViewGroup.LayoutParams.WRAP_CONTENT));

        Button manualToggle=button("手动连接设备",false);LinearLayout.LayoutParams mtp=match(dp(50));mtp.topMargin=dp(16);root.addView(manualToggle,mtp);
        LinearLayout manual=card();manual.setVisibility(View.GONE);LinearLayout.LayoutParams mp=match(ViewGroup.LayoutParams.WRAP_CONTENT);mp.topMargin=dp(10);root.addView(manual,mp);
        TextView manualTitle=text("手动连接",18,INK);manualTitle.setTypeface(null,Typeface.BOLD);manual.addView(manualTitle,match(dp(42)));
        manual.addView(label("设备地址、IP:端口或完整分享链接"),match(dp(30)));EditText host=input(preferences.getString("host",""),false);host.setHint("192.168.1.82:53317");manual.addView(host,match(dp(54)));
        TextView codeLabel=label("对方配对码");LinearLayout.LayoutParams cp=match(dp(44));cp.topMargin=dp(10);manual.addView(codeLabel,cp);EditText code=input(preferences.getString("code","123456"),true);manual.addView(code,match(dp(54)));
        Button connect=button("连接该设备",true);LinearLayout.LayoutParams bp=match(dp(50));bp.topMargin=dp(18);manual.addView(connect,bp);connect.setOnClickListener(v->connectToHost(host.getText().toString(),code.getText().toString(),connect));
        manualToggle.setOnClickListener(v->{boolean show=manual.getVisibility()!=View.VISIBLE;manual.setVisibility(show?View.VISIBLE:View.GONE);manualToggle.setText(show?"收起手动连接":"手动连接设备");if(show)scroll.post(()->scroll.smoothScrollTo(0,manual.getTop()));});
        TextView hint=text("仅显示同一 Wi-Fi 中正在运行 LocalLink 的设备",12,MUTED);hint.setGravity(Gravity.CENTER);LinearLayout.LayoutParams hp=match(dp(44));hp.topMargin=dp(8);root.addView(hint,hp);
        setContentView(scroll);handler.postDelayed(peerRefresh,600);handler.postDelayed(()->{if(hostStatus!=null)hostStatus.setText((LocalLinkService.isHostRunning()?"● 服务在线":"● 服务启动失败")+"\n"+LocalLinkService.wifiAddress()+":"+MobileHostServer.PORT+"  ·  配对码 "+localCode);},900);
    }

    private void renderPeers(){
        if(peersContainer==null)return;peersContainer.removeAllViews();ArrayList<LocalLinkService.Peer> peers=LocalLinkService.peers();
        if(peers.isEmpty()){TextView empty=text("暂未发现其他设备",14,MUTED);empty.setGravity(Gravity.CENTER);empty.setBackground(shape(Color.WHITE,LINE,14));peersContainer.addView(empty,match(dp(82)));return;}
        for(LocalLinkService.Peer peer:peers){LinearLayout row=card();LinearLayout.LayoutParams rp=match(ViewGroup.LayoutParams.WRAP_CONTENT);rp.bottomMargin=dp(10);peersContainer.addView(row,rp);LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);row.addView(top,match(dp(58)));TextView info=text(peer.name+"\n"+peer.ip+":"+peer.port,14,INK);info.setLineSpacing(0,1.35f);info.setTypeface(null,Typeface.BOLD);top.addView(info,new LinearLayout.LayoutParams(0,dp(56),1));Button connect=button("连接",true);top.addView(connect,new LinearLayout.LayoutParams(dp(86),dp(44)));connect.setOnClickListener(v->connectToHost(peer.ip+":"+peer.port,preferences.getString("code","123456"),connect));}
    }

    private void addTrustedDevices(LinearLayout root){try{JSONArray trusted=new JSONArray(preferences.getString("trusted_devices","[]"));if(trusted.length()==0)return;TextView heading=text("已信任设备",18,INK);heading.setTypeface(null,Typeface.BOLD);LinearLayout.LayoutParams hp=match(dp(50));hp.topMargin=dp(18);root.addView(heading,hp);for(int i=0;i<trusted.length();i++){JSONObject item=trusted.getJSONObject(i);String host=item.optString("host"),code=item.optString("code","123456"),name=item.optString("name",host);LinearLayout row=card();LinearLayout.LayoutParams rp=match(dp(82));rp.bottomMargin=dp(10);root.addView(row,rp);LinearLayout line=new LinearLayout(this);line.setGravity(Gravity.CENTER_VERTICAL);row.addView(line,match(dp(44)));TextView info=text(name+"\n"+host,13,INK);info.setTypeface(null,Typeface.BOLD);line.addView(info,new LinearLayout.LayoutParams(0,dp(44),1));Button connect=button("发送/连接",true);line.addView(connect,new LinearLayout.LayoutParams(dp(112),dp(42)));connect.setOnClickListener(v->connectToHost(host,code,connect));}}catch(Exception ignored){preferences.edit().remove("trusted_devices").apply();}}

    private void rememberTrusted(String host,String code,String name){try{JSONArray old=new JSONArray(preferences.getString("trusted_devices","[]")),next=new JSONArray();next.put(new JSONObject().put("host",host).put("code",code).put("name",name));for(int i=0;i<old.length()&&next.length()<8;i++){JSONObject item=old.getJSONObject(i);if(!host.equals(item.optString("host")))next.put(item);}preferences.edit().putString("trusted_devices",next.toString()).apply();}catch(Exception ignored){}}

    private void openLocalInbox(){
        if(!LocalLinkService.isHostRunning()){toast("本机收件箱启动失败，端口可能被其他程序占用");return;}
        String code=preferences.getString("local_code","123456");String base="http://127.0.0.1:"+MobileHostServer.PORT;if(hasPendingShare())sendPending(base,code,null,"我的收件箱");else openLink(base+"/?code="+code+"&client="+encoded(deviceName()),"我的收件箱");
    }

    private void connectToHost(String raw,String fallbackCode,Button connect){
        String candidate=raw.trim().matches("^[a-zA-Z][a-zA-Z0-9+.-]*://.*")?raw.trim():"http://"+raw.trim();Uri parsed=Uri.parse(candidate);String hostname=parsed.getHost();int port=parsed.getPort();String host=hostname==null?"":hostname+(port>0?":"+port:":53317");String embedded=parsed.getQueryParameter("code");String code=embedded!=null&&!embedded.isEmpty()?embedded:fallbackCode.trim();
        if(host.isEmpty()||!code.matches("\\d{6}")){toast("地址或配对码格式无效");return;}if(!bindToWifi()){toast("未检测到可用 Wi-Fi");return;}
        preferences.edit().putString("host",host).putString("code",code).apply();String base="http://"+host;String target=base+"/?code="+encoded(code)+"&client="+encoded(deviceName());connect.setEnabled(false);connect.setText("检测中…");
        new Thread(()->{String error=null;String peerName="远端设备";try{HttpURLConnection connection=(HttpURLConnection)new URL(base+"/api/health").openConnection();connection.setConnectTimeout(4000);connection.setReadTimeout(4000);if(connection.getResponseCode()!=200)error="目标设备未响应 LocalLink";else try(InputStream input=connection.getInputStream();ByteArrayOutputStream data=new ByteArrayOutputStream()){byte[] buffer=new byte[2048];int read;while((read=input.read(buffer))>=0)data.write(buffer,0,read);peerName=new JSONObject(data.toString("UTF-8")).optString("name",peerName);}connection.disconnect();}catch(Exception failure){error="无法访问 "+host+"，请确认双方位于同一 Wi-Fi 网段";}String finalError=error;String finalName=peerName;runOnUiThread(()->{connect.setEnabled(true);connect.setText("连接");if(finalError==null){rememberTrusted(host,code,finalName);if(hasPendingShare())sendPending(base,code,connect,finalName);else openLink(target,finalName);}else toast(finalError);});},"locallink-preflight").start();
    }

    private void sendPending(String base,String code,Button button,String receiver){if(button!=null){button.setEnabled(false);button.setText("发送中…");}new Thread(()->{String error=null;try{if(!pendingText.trim().isEmpty()){byte[] body=new JSONObject().put("text",pendingText).put("sender",deviceName()).toString().getBytes(StandardCharsets.UTF_8);HttpURLConnection connection=(HttpURLConnection)new URL(base+"/api/text").openConnection();connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setConnectTimeout(6000);connection.setReadTimeout(15000);connection.setRequestProperty("X-LocalLink-Code",code);connection.setRequestProperty("Content-Type","application/json; charset=utf-8");connection.setFixedLengthStreamingMode(body.length);try(OutputStream out=connection.getOutputStream()){out.write(body);}if(connection.getResponseCode()>=300)throw new Exception("文字发送失败");connection.disconnect();}for(Uri uri:new ArrayList<>(pendingUris))sendSharedFile(base,code,uri);}catch(Exception failure){error=failure.getMessage()==null?"发送失败":failure.getMessage();}String finalError=error;runOnUiThread(()->{if(button!=null){button.setEnabled(true);button.setText("连接");}if(finalError==null){pendingText="";pendingUris.clear();toast("内容已发送到 "+receiver);openLink(base+"/?code="+encoded(code)+"&client="+encoded(deviceName()),receiver);}else toast(finalError);});},"locallink-system-share").start();}

    private void sendSharedFile(String base,String code,Uri uri)throws Exception{String name=sharedName(uri);long size=sharedSize(uri);if(size<0)throw new Exception("无法读取 "+name+" 的大小");HttpURLConnection connection=(HttpURLConnection)new URL(base+"/api/upload").openConnection();connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setConnectTimeout(8000);connection.setReadTimeout(120000);connection.setRequestProperty("X-LocalLink-Code",code);connection.setRequestProperty("X-Filename",encoded(name));connection.setRequestProperty("X-Sender",encoded(deviceName()));connection.setFixedLengthStreamingMode(size);try(InputStream input=getContentResolver().openInputStream(uri);OutputStream output=connection.getOutputStream()){if(input==null)throw new Exception("无法读取 "+name);byte[] buffer=new byte[1024*1024];int read;while((read=input.read(buffer))>=0)output.write(buffer,0,read);}if(connection.getResponseCode()>=300)throw new Exception(name+" 发送失败");connection.disconnect();}
    private String sharedName(Uri uri){try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())return cursor.getString(0);}catch(Exception ignored){}String value=uri.getLastPathSegment();return value==null?"shared-file":value;}
    private long sharedSize(Uri uri){try(AssetFileDescriptor descriptor=getContentResolver().openAssetFileDescriptor(uri,"r")){if(descriptor!=null)return descriptor.getLength();}catch(Exception ignored){}try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){if(cursor!=null&&cursor.moveToFirst()&&!cursor.isNull(0))return cursor.getLong(0);}catch(Exception ignored){}return -1;}

    private boolean bindToWifi(){ConnectivityManager manager=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);for(Network network:manager.getAllNetworks()){NetworkCapabilities capabilities=manager.getNetworkCapabilities(network);if(capabilities!=null&&capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))return manager.bindProcessToNetwork(network);}return false;}
    private String deviceName(){return preferences.getString("device_name",Build.MANUFACTURER+" "+Build.MODEL);}
    private static String encoded(String value){return URLEncoder.encode(value,StandardCharsets.UTF_8);}

    private void openLink(String url,String title){
        handler.removeCallbacks(peerRefresh);peersContainer=null;LinearLayout shell=new LinearLayout(this);shell.setOrientation(LinearLayout.VERTICAL);shell.setBackgroundColor(Color.WHITE);shell.setPadding(0,dp(24),0,0);LinearLayout bar=new LinearLayout(this);bar.setGravity(Gravity.CENTER_VERTICAL);bar.setPadding(dp(10),dp(4),dp(10),dp(4));
        Button close=button("设备列表",false);close.setOnClickListener(v->showDeviceScreen());bar.addView(close,new LinearLayout.LayoutParams(dp(96),dp(46)));TextView label=text(title,14,INK);label.setTypeface(null,Typeface.BOLD);label.setGravity(Gravity.CENTER);bar.addView(label,new LinearLayout.LayoutParams(0,dp(50),1));Button refresh=button("刷新",false);refresh.setOnClickListener(v->webView.reload());bar.addView(refresh,new LinearLayout.LayoutParams(dp(72),dp(46)));shell.addView(bar,match(dp(58)));
        ProgressBar progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(BLUE));shell.addView(progress,match(dp(3)));webView=new WebView(this);configureWebView(progress);shell.addView(webView,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));setContentView(shell);webView.loadUrl(url);
    }

    private void configureWebView(ProgressBar progress){webView.setBackgroundColor(Color.WHITE);webView.getSettings().setJavaScriptEnabled(true);webView.getSettings().setDomStorageEnabled(true);webView.getSettings().setAllowContentAccess(true);webView.getSettings().setAllowFileAccess(true);CookieManager.getInstance().setAcceptCookie(true);webView.setWebViewClient(new WebViewClient(){@Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())toast("连接已中断，请返回设备列表重试");}});webView.setWebChromeClient(new WebChromeClient(){@Override public void onProgressChanged(WebView view,int value){progress.setProgress(value);progress.setVisibility(value==100?View.GONE:View.VISIBLE);}@Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){if(fileCallback!=null)fileCallback.onReceiveValue(null);fileCallback=callback;Intent intent=params.createIntent();intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);startActivityForResult(intent,FILE_CHOOSER_REQUEST);return true;}});webView.setDownloadListener((url,userAgent,disposition,mime,length)->{try{DownloadManager.Request request=new DownloadManager.Request(Uri.parse(url));request.setMimeType(mime);request.addRequestHeader("User-Agent",userAgent);request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,android.webkit.URLUtil.guessFileName(url,disposition,mime));((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(request);toast("文件已保存到系统下载目录");}catch(Exception error){toast("下载失败："+error.getMessage());}});}

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){super.onActivityResult(requestCode,resultCode,data);if(requestCode!=FILE_CHOOSER_REQUEST||fileCallback==null)return;Uri[] result=null;if(resultCode==RESULT_OK&&data!=null){if(data.getClipData()!=null){result=new Uri[data.getClipData().getItemCount()];for(int i=0;i<result.length;i++)result[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)result=new Uri[]{data.getData()};}fileCallback.onReceiveValue(result);fileCallback=null;}
    @Override public void onBackPressed(){if(webView!=null&&webView.canGoBack())webView.goBack();else if(webView!=null)showDeviceScreen();else super.onBackPressed();}
    @Override protected void onDestroy(){handler.removeCallbacks(peerRefresh);if(webView!=null)webView.destroy();super.onDestroy();}
    private void toast(String message){Toast.makeText(this,message,Toast.LENGTH_LONG).show();}
}
