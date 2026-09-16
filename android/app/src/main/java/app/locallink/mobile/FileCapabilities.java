package app.locallink.mobile;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

public final class FileCapabilities {
    public static final String APK_MIME = "application/vnd.android.package-archive";

    public static final class Result {
        public final String category;
        public final String mimeType;
        public final List<String> actions;
        public final boolean installable;
        Result(String category, String mimeType, List<String> actions, boolean installable) {
            this.category=category; this.mimeType=mimeType; this.actions=Collections.unmodifiableList(actions); this.installable=installable;
        }
    }

    private FileCapabilities() {}

    public static Result resolve(String name, String suppliedMime) {
        String lower=name.toLowerCase(Locale.ROOT), mime=suppliedMime==null||suppliedMime.isEmpty()?mimeFor(name):suppliedMime;
        if(matches(lower,".png",".jpg",".jpeg",".gif",".webp",".bmp",".svg"))return result("image",mime,false,"preview_inline","download");
        if(matches(lower,".mp4",".webm",".mov",".m4v"))return result("video",mime,false,"preview_inline","download");
        if(matches(lower,".mp3",".wav",".ogg",".m4a",".aac",".flac"))return result("audio",mime,false,"preview_inline","download");
        if(lower.endsWith(".pdf"))return result("pdf",mime,false,"preview_inline","open_external","download");
        if(matches(lower,".txt",".md",".json",".csv",".log",".xml",".html",".htm",".yaml",".yml"))return result("text",mime,false,"preview_inline","open_external","download");
        if(matches(lower,".doc",".docx",".odt",".rtf"))return result("document",mime,false,"open_external","download");
        if(matches(lower,".xls",".xlsx",".ods"))return result("spreadsheet",mime,false,"open_external","download");
        if(matches(lower,".ppt",".pptx",".odp"))return result("presentation",mime,false,"open_external","download");
        if(lower.endsWith(".apk")){boolean safe=APK_MIME.equals(mime);return safe?result("android-package",mime,true,"install","download"):result("android-package",mime,false,"download");}
        return result("binary",mime,false,"download");
    }

    public static String mimeFor(String name) {
        String lower=name.toLowerCase(Locale.ROOT);
        if(lower.endsWith(".apk"))return APK_MIME;
        if(lower.endsWith(".docx"))return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if(lower.endsWith(".doc"))return "application/msword";
        if(lower.endsWith(".xlsx"))return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        if(lower.endsWith(".xls"))return "application/vnd.ms-excel";
        if(lower.endsWith(".pptx"))return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
        if(lower.endsWith(".ppt"))return "application/vnd.ms-powerpoint";
        if(lower.endsWith(".odt"))return "application/vnd.oasis.opendocument.text";
        if(lower.endsWith(".ods"))return "application/vnd.oasis.opendocument.spreadsheet";
        if(lower.endsWith(".odp"))return "application/vnd.oasis.opendocument.presentation";
        String value=java.net.URLConnection.guessContentTypeFromName(name);
        return value==null?"application/octet-stream":value;
    }

    private static Result result(String category,String mime,boolean installable,String... actions){return new Result(category,mime,Arrays.asList(actions),installable);}
    private static boolean matches(String value,String... suffixes){for(String suffix:suffixes)if(value.endsWith(suffix))return true;return false;}
}
