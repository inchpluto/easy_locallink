package app.locallink.mobile;

import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public final class NativeFileBridge {
    private final MainActivity activity;

    NativeFileBridge(MainActivity activity) { this.activity = activity; }

    /** WebView pages on HTTP cannot always use navigator.clipboard. Keep copying native and explicit. */
    @JavascriptInterface public boolean copyText(String value) {
        if (value == null || value.isEmpty()) return false;
        try {
            ClipboardManager clipboard = (ClipboardManager) activity.getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("LocalLink", value));
            return true;
        } catch (Exception error) { return false; }
    }

    @JavascriptInterface public void openRecord(String recordId, String action) {
        prepare(recordId, "install".equals(action));
    }

    @JavascriptInterface public void openExternal(String recordId) { prepare(recordId, false); }
    @JavascriptInterface public void installApk(String recordId) { prepare(recordId, true); }

    private void prepare(String recordId, boolean install) {
        activity.runOnUiThread(() -> {
            String pageUrl = activity.currentPageUrl();
            message("正在准备文件…");
            new Thread(() -> {
                File file = LocalLinkService.recordFile(recordId);
                if (file == null) file = downloadRemote(recordId, pageUrl);
                File resolved = file;
                activity.runOnUiThread(() -> {
                    if (resolved == null) { message("文件已被移除或下载失败"); return; }
                    if (install) confirmInstall(resolved); else launchExternal(resolved);
                });
            }, "locallink-native-open").start();
        });
    }

    private void launchExternal(File file) {
        Uri uri = fileUri(file);
        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, FileCapabilities.mimeFor(file.getName()))
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try { activity.startActivity(intent); }
        catch (ActivityNotFoundException error) { message("未找到可打开此文件的应用"); }
    }

    private void confirmInstall(File file) {
        if (!file.getName().toLowerCase().endsWith(".apk")
                || activity.getPackageManager().getPackageArchiveInfo(file.getAbsolutePath(), 0) == null) {
            message("安装包无效或已被移除"); return;
        }
        new AlertDialog.Builder(activity)
                .setTitle("安装应用")
                .setMessage("即将把“" + file.getName().substring(file.getName().indexOf("--") + 2) + "”交给 Android 系统安装器。请只安装来自可信设备的文件。")
                .setNegativeButton("取消", null)
                .setPositiveButton("继续", (dialog, which) -> launchInstaller(file))
                .show();
    }

    private File downloadRemote(String recordId, String pageUrl) {
        try {
            Uri page = Uri.parse(pageUrl);
            String code = page.getQueryParameter("code");
            if (page.getHost() == null || code == null || !recordId.matches("[A-Za-z0-9-]{8,64}")) return null;
            String base = page.getScheme() + "://" + page.getAuthority();
            HttpURLConnection status = connection(base + "/api/status", code);
            JSONObject payload;
            try (InputStream input = status.getInputStream()) { payload = new JSONObject(readText(input)); }
            finally { status.disconnect(); }
            String name = "received-file";
            JSONArray history = payload.optJSONArray("history");
            if (history != null) for (int i=0;i<history.length();i++) {
                JSONObject item=history.getJSONObject(i);
                if (recordId.equals(item.optString("id"))) { name=item.optString("name",name); break; }
            }
            name = new File(name.replace('\\','/')).getName().replaceAll("[<>:\"/\\\\|?*\\x00-\\x1f]","_");
            File directory = new File(activity.getCacheDir(), "native-open"); directory.mkdirs();
            File target = new File(directory, recordId + "--" + name), part = new File(target.getPath()+".part");
            HttpURLConnection download = connection(base + "/api/download/" + recordId, code);
            try (InputStream input=download.getInputStream(); FileOutputStream output=new FileOutputStream(part)) {
                byte[] buffer=new byte[1024*1024]; int read; while((read=input.read(buffer))>=0)output.write(buffer,0,read);
            } finally { download.disconnect(); }
            if (!part.renameTo(target)) { part.delete(); return null; }
            return target;
        } catch (Exception error) { return null; }
    }

    private HttpURLConnection connection(String url,String code)throws Exception {
        HttpURLConnection value=(HttpURLConnection)new URL(url).openConnection();value.setConnectTimeout(6000);value.setReadTimeout(120000);value.setRequestProperty("X-LocalLink-Code",code);return value;
    }

    private String readText(InputStream input)throws Exception {java.io.ByteArrayOutputStream output=new java.io.ByteArrayOutputStream();byte[] buffer=new byte[8192];int read;while((read=input.read(buffer))>=0)output.write(buffer,0,read);return output.toString("UTF-8");}

    private void launchInstaller(File file) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !activity.getPackageManager().canRequestPackageInstalls()) {
            Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName()));
            activity.startActivity(settings);
            message("请允许 LocalLink 安装未知应用，然后再次点击安装");
            return;
        }
        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(fileUri(file), FileCapabilities.APK_MIME)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try { activity.startActivity(intent); }
        catch (ActivityNotFoundException error) { message("系统安装器不可用"); }
    }

    private Uri fileUri(File file) {
        return FileProvider.getUriForFile(activity, activity.getPackageName() + ".files", file);
    }

    private void message(String value) {
        Toast.makeText(activity, value, Toast.LENGTH_LONG).show();
    }
}
