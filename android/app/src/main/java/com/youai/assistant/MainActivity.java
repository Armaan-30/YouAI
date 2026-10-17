package com.youai.assistant;

import android.Manifest;
import android.app.*;
import android.os.Bundle;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.speech.tts.*;
import android.webkit.*;
import android.widget.*;
import org.json.JSONObject;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.util.*;

public class MainActivity extends Activity {
 private WebView web;
 private TextToSpeech tts;
 private boolean speechReady;
 private String origin="", token="";
 private ValueCallback<Uri[]> upload;
 private PermissionRequest microphone;
 private android.content.SharedPreferences prefs;
 @Override public void onCreate(Bundle state) {
  super.onCreate(state); prefs=getSharedPreferences("pairing",MODE_PRIVATE);
  tts=new TextToSpeech(this,status->{speechReady=status==TextToSpeech.SUCCESS; if(speechReady){
   tts.setLanguage(Locale.US); tts.setSpeechRate(.9f);
   String selected=prefs.getString("voice","");
   for(Voice v:tts.getVoices()) if(v.getName().equals(selected)&&!v.isNetworkConnectionRequired()) tts.setVoice(v);
   tts.setOnUtteranceProgressListener(new UtteranceProgressListener(){
    public void onStart(String id){} public void onDone(String id){complete(id);} public void onError(String id){complete(id);}
   });
  }});
  if(getIntent().getData()!=null) pairing(getIntent().getData().toString());
  else if(prefs.contains("url")) connect(); else pairingScreen();
 }
 @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);if(intent.getData()!=null)pairing(intent.getData().toString());}
 private void pairingScreen(){
  LinearLayout box=new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);box.setPadding(32,64,32,32);
  TextView title=new TextView(this);title.setText("YouAI • Connect to your laptop\nRun start-phone.ps1, then copy the pairing link from the laptop's Conversation panel.");box.addView(title);
  EditText link=new EditText(this);link.setHint("youai://pair?…");box.addView(link);
  Button button=new Button(this);button.setText("Pair laptop");button.setOnClickListener(v->pairing(link.getText().toString().trim()));box.addView(button);setContentView(box);
 }
 private void pairing(String link){try{
  Uri uri=Uri.parse(link);if(!"youai".equals(uri.getScheme())||!"pair".equals(uri.getHost()))throw new Exception();
  String url=uri.getQueryParameter("url"), secret=uri.getQueryParameter("token");Uri server=Uri.parse(url);
  if(!"https".equals(server.getScheme())||server.getPort()!=8768||server.getUserInfo()!=null||!server.getHost().matches("[0-9.]+")||!server.getPath().isEmpty()||server.getQuery()!=null||server.getFragment()!=null||secret==null||!secret.matches("[A-Za-z0-9_-]{40,100}"))throw new Exception();
  java.net.InetAddress address=java.net.InetAddress.getByName(server.getHost());if(!address.isSiteLocalAddress())throw new Exception();
  java.security.cert.Certificate cert=CertificateFactory.getInstance("X.509").generateCertificate(getResources().openRawResource(com.youai.assistant.R.raw.laptop_ca));
  StringBuilder pin=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(cert.getEncoded()))pin.append(String.format(Locale.ROOT,"%02x",b));
  if(!pin.toString().equals(uri.getQueryParameter("pin")))throw new Exception();
  new AlertDialog.Builder(this).setTitle("Connect to your laptop?").setMessage(url).setPositiveButton("Connect",(d,w)->{prefs.edit().putString("url",url).putString("token",secret).apply();connect();}).setNegativeButton("Cancel",(d,w)->pairingScreen()).show();
 }catch(Exception e){Toast.makeText(this,"Invalid pairing link, or APK belongs to another laptop.",Toast.LENGTH_LONG).show();pairingScreen();}}
 private boolean trusted(String url){try{Uri u=Uri.parse(url);return origin.equals(u.getScheme()+"://"+u.getEncodedAuthority());}catch(Exception e){return false;}}
 private void connect(){
  origin=prefs.getString("url","");token=prefs.getString("token","");
  if(web!=null)web.destroy();web=new WebView(this);
  web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);
  web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
  web.getSettings().setMediaPlaybackRequiresUserGesture(false);
  web.addJavascriptInterface(new Bridge(),"NativeYou");
  web.setWebViewClient(new WebViewClient(){
   public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){return !trusted(req.getUrl().toString());}
   public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest req){if(!trusted(req.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));return null;}
   public void onReceivedError(WebView v,WebResourceRequest req,WebResourceError error){if(req.isForMainFrame())runOnUiThread(()->new AlertDialog.Builder(MainActivity.this).setTitle("Laptop unavailable").setMessage("Keep the laptop awake, run start-phone.ps1, and connect both devices to the same Wi-Fi. Pair again if its address changed.").setPositiveButton("Retry",(d,w)->web.loadUrl(origin)).setNegativeButton("Pair again",(d,w)->pairingScreen()).show());}
  });
  web.setWebChromeClient(new WebChromeClient(){
   public void onPermissionRequest(PermissionRequest req){runOnUiThread(()->{
    if(!trusted(req.getOrigin().toString())){req.deny();return;}
    if(!Arrays.asList(req.getResources()).contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)){req.deny();return;}
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)req.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
    else{if(microphone!=null)microphone.deny();microphone=req;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},7);}
   });}
   public void onPermissionRequestCanceled(PermissionRequest req){if(microphone==req)microphone=null;}
   public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams params){if(upload!=null)upload.onReceiveValue(null);upload=callback;Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);pick.addCategory(Intent.CATEGORY_OPENABLE);pick.setType("*/*");pick.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","text/plain","text/markdown"});startActivityForResult(pick,8);return true;}
  });
  LinearLayout box=new LinearLayout(this);box.setFitsSystemWindows(true);box.setOrientation(LinearLayout.VERTICAL);Button settings=new Button(this);settings.setText("Connection / Voice");settings.setOnClickListener(v->settings());box.addView(settings);box.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(box);web.loadUrl(origin);
 }
 private void settings(){new AlertDialog.Builder(this).setItems(new String[]{"Reconnect","Choose installed voice","Forget laptop"},(d,n)->{
  if(n==0)web.reload();else if(n==2){prefs.edit().remove("url").remove("token").apply();token="";web.destroy();web=null;pairingScreen();}
  else if(speechReady){List<Voice> voices=new ArrayList<>();for(Voice v:tts.getVoices())if(!v.isNetworkConnectionRequired()&&v.getLocale().getLanguage().equals("en"))voices.add(v);
   voices.sort(Comparator.comparing(Voice::getName));String[] names=new String[voices.size()];for(int i=0;i<names.length;i++)names[i]=voices.get(i).getName();
   new AlertDialog.Builder(this).setTitle("Local voice (tap to preview)").setItems(names,(x,i)->{Voice v=voices.get(i);tts.setVoice(v);prefs.edit().putString("voice",v.getName()).apply();tts.speak("Hi, I'm You. How can I help you today?",TextToSpeech.QUEUE_FLUSH,null,"preview");}).show();
  }
 }).show();}
 private void complete(String id){runOnUiThread(()->{if(web!=null)web.evaluateJavascript("window.onYouSpeech && window.onYouSpeech("+JSONObject.quote(id)+")",null);});}
 private class Bridge {
  @JavascriptInterface public String getToken(){return token;}
  @JavascriptInterface public void stop(){runOnUiThread(()->tts.stop());}
  @JavascriptInterface public void speak(String text,String id){runOnUiThread(()->{
   Voice voice=tts.getVoice();if(!speechReady||voice==null||voice.isNetworkConnectionRequired()){Toast.makeText(MainActivity.this,"Choose an installed offline voice in Connection / Voice.",Toast.LENGTH_LONG).show();complete(id);return;}
   if(tts.speak(text,TextToSpeech.QUEUE_ADD,null,id)==TextToSpeech.ERROR)complete(id);
  });}
 }
 @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==7&&microphone!=null){if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)microphone.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});else microphone.deny();microphone=null;}}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==8&&upload!=null){upload.onReceiveValue(result==RESULT_OK&&data!=null?new Uri[]{data.getData()}:null);upload=null;}}
 @Override protected void onPause(){super.onPause();if(tts!=null)tts.stop();if(web!=null){web.evaluateJavascript("typeof stopAll==='function' && stopAll()",null);web.onPause();}}
 @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
 @Override protected void onDestroy(){if(upload!=null)upload.onReceiveValue(null);if(web!=null)web.destroy();if(tts!=null)tts.shutdown();super.onDestroy();}
}
