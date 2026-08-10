package app.locallink.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.MulticastSocket;
import java.net.NetworkInterface;
import java.net.URL;
import java.net.HttpURLConnection;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class LocalLinkService extends Service {
    private static final String CHANNEL = "locallink_host";
    private static final String RECEIVE_CHANNEL = "locallink_received";
    private static final String GROUP = "239.255.42.99";
    private static final int DISCOVERY_PORT = 53318;
    private static final ConcurrentHashMap<String,Peer> peers = new ConcurrentHashMap<>();
    private static volatile LocalLinkService instance;
    private static volatile String ownId = "";
    private MobileHostServer host;
    private volatile boolean running;
    private MulticastSocket discoverySocket;
    private WifiManager.MulticastLock multicastLock;
    private final ExecutorService scanPool = Executors.newFixedThreadPool(32);

    static final class Peer {
        final String id,name,ip; final int port; volatile long seen;
        Peer(String id,String name,String ip,int port){this.id=id;this.name=name;this.ip=ip;this.port=port;this.seen=System.currentTimeMillis();}
        JSONObject json(){try{return new JSONObject().put("id",id).put("name",name).put("ip",ip).put("port",port).put("last_seen",seen/1000.0);}catch(Exception error){return new JSONObject();}}
    }

    @Override public void onCreate() {
        super.onCreate(); instance=this; running=true;
        SharedPreferences preferences=getSharedPreferences("locallink",MODE_PRIVATE);
        ownId=preferences.getString("device_id","");
        if(ownId.isEmpty()){ownId=UUID.randomUUID().toString().replace("-","");preferences.edit().putString("device_id",ownId).apply();}
        String name=preferences.getString("device_name",Build.MANUFACTURER+" "+Build.MODEL);
        String code=preferences.getString("local_code","123456");
        createNotification(name);
        try{host=new MobileHostServer(this,name,code);host.start();}catch(Exception error){host=null;}
        startDiscovery(name);
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId){return START_STICKY;}
    @Override public IBinder onBind(Intent intent){return null;}
    @Override public void onDestroy(){running=false;instance=null;if(host!=null)host.stop();try{if(discoverySocket!=null)discoverySocket.close();}catch(Exception ignored){}if(multicastLock!=null&&multicastLock.isHeld())multicastLock.release();scanPool.shutdownNow();super.onDestroy();}

    private void createNotification(String name){
        NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(Build.VERSION.SDK_INT>=26)manager.createNotificationChannel(new NotificationChannel(CHANNEL,"LocalLink 本机收件箱",NotificationManager.IMPORTANCE_LOW));
        if(Build.VERSION.SDK_INT>=26)manager.createNotificationChannel(new NotificationChannel(RECEIVE_CHANNEL,"LocalLink 接收通知",NotificationManager.IMPORTANCE_DEFAULT));
        Intent open=new Intent(this,MainActivity.class);PendingIntent pending=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(this,CHANNEL).setSmallIcon(app.locallink.mobile.R.drawable.ic_launcher).setContentTitle("LocalLink 本机收件箱在线").setContentText(name+" · "+wifiAddress()+":"+MobileHostServer.PORT).setOngoing(true).setContentIntent(pending).build();
        startForeground(53317,notification);
    }

    static void notifyReceived(String title,String detail){LocalLinkService service=instance;if(service==null)return;NotificationManager manager=(NotificationManager)service.getSystemService(NOTIFICATION_SERVICE);Intent open=new Intent(service,MainActivity.class);PendingIntent pending=PendingIntent.getActivity(service,1,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Notification notification=new Notification.Builder(service,RECEIVE_CHANNEL).setSmallIcon(app.locallink.mobile.R.drawable.ic_launcher).setContentTitle(title).setContentText(detail).setAutoCancel(true).setContentIntent(pending).build();manager.notify((int)(System.currentTimeMillis()&0x7fffffff),notification);}

    private void startDiscovery(String name){
        WifiManager wifi=(WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);multicastLock=wifi.createMulticastLock("locallink-discovery");multicastLock.setReferenceCounted(false);multicastLock.acquire();
        Thread listener=new Thread(()->{
            try{discoverySocket=new MulticastSocket(null);discoverySocket.setReuseAddress(true);discoverySocket.bind(new InetSocketAddress(DISCOVERY_PORT));InetAddress group=InetAddress.getByName(GROUP);NetworkInterface wifiInterface=NetworkInterface.getByName("wlan0");if(wifiInterface!=null)discoverySocket.joinGroup(new InetSocketAddress(group,DISCOVERY_PORT),wifiInterface);else discoverySocket.joinGroup(group);discoverySocket.setSoTimeout(1500);byte[] buffer=new byte[4096];
                while(running){try{DatagramPacket packet=new DatagramPacket(buffer,buffer.length);discoverySocket.receive(packet);JSONObject value=new JSONObject(new String(packet.getData(),0,packet.getLength(),java.nio.charset.StandardCharsets.UTF_8));updatePeer(value,packet.getAddress().getHostAddress());}catch(java.net.SocketTimeoutException ignored){}catch(Exception ignored){}}
            }catch(Exception ignored){}
        },"locallink-discovery-listen");listener.setDaemon(true);listener.start();
        Thread announce=new Thread(()->{while(running){try{JSONObject value=new JSONObject().put("service","locallink").put("version","2").put("id",ownId).put("name",name).put("port",MobileHostServer.PORT);byte[] data=value.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);try(MulticastSocket sender=new MulticastSocket()){sender.setTimeToLive(1);NetworkInterface wifiInterface=NetworkInterface.getByName("wlan0");if(wifiInterface!=null)sender.setNetworkInterface(wifiInterface);sender.send(new DatagramPacket(data,data.length,InetAddress.getByName(GROUP),DISCOVERY_PORT));}}catch(Exception ignored){}try{Thread.sleep(3000);}catch(InterruptedException stop){return;}}},"locallink-discovery-announce");announce.setDaemon(true);announce.start();
    }

    private static void updatePeer(JSONObject value,String ip){
        if(!"locallink".equals(value.optString("service")))return;String id=value.optString("id");if(id.isEmpty()||id.equals(ownId))return;
        Peer existing=peers.get(id);if(existing==null)peers.put(id,new Peer(id,value.optString("name","LocalLink"),ip,value.optInt("port",MobileHostServer.PORT)));else existing.seen=System.currentTimeMillis();
    }

    public static JSONArray peersJson(){JSONArray result=new JSONArray();long now=System.currentTimeMillis();for(Map.Entry<String,Peer> entry:peers.entrySet()){if(now-entry.getValue().seen>20000){peers.remove(entry.getKey());continue;}result.put(entry.getValue().json());}return result;}
    public static ArrayList<Peer> peers(){ArrayList<Peer> result=new ArrayList<>();long now=System.currentTimeMillis();for(Peer peer:peers.values())if(now-peer.seen<=20000)result.add(peer);return result;}
    public static boolean isHostRunning(){return instance!=null&&instance.host!=null&&instance.host.isRunning();}
    public static String deviceId(){return ownId;}

    public static void scanSubnet(){if(instance==null)return;String own=wifiAddress();String[] octets=own.split("\\.");if(octets.length!=4)return;String prefix=octets[0]+"."+octets[1]+"."+octets[2]+".";for(int i=1;i<255;i++){String ip=prefix+i;if(ip.equals(own))continue;instance.scanPool.execute(()->probe(ip));}}
    private static void probe(String ip){try{HttpURLConnection connection=(HttpURLConnection)new URL("http://"+ip+":"+MobileHostServer.PORT+"/api/health").openConnection();connection.setConnectTimeout(300);connection.setReadTimeout(500);if(connection.getResponseCode()==200){try(InputStream in=connection.getInputStream();ByteArrayOutputStream data=new ByteArrayOutputStream()){byte[] buffer=new byte[2048];int read;while((read=in.read(buffer))>=0)data.write(buffer,0,read);updatePeer(new JSONObject(data.toString("UTF-8")),ip);}}connection.disconnect();}catch(Exception ignored){}}

    public static String wifiAddress(){String fallback="";try{for(NetworkInterface network:Collections.list(NetworkInterface.getNetworkInterfaces())){if(!network.isUp()||network.isLoopback())continue;for(InetAddress address:Collections.list(network.getInetAddresses()))if(address instanceof Inet4Address&&address.isSiteLocalAddress()){String value=address.getHostAddress();if(network.getName().startsWith("wlan"))return value;if(fallback.isEmpty()&&(value.startsWith("192.168.")||value.startsWith("10.")||value.startsWith("172.")))fallback=value;}}}catch(Exception ignored){}return fallback.isEmpty()?"127.0.0.1":fallback;}
}
