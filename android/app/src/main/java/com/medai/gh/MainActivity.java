package com.medai.gh;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.AsyncTask;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.constraintlayout.widget.ConstraintLayout;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.google.android.material.textfield.TextInputEditText;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "MedAIPrefs";
    private static final String KEY_SERVER_URL = "ServerURL";

    private Toolbar toolbar;
    private ScrollView layoutConfig;
    private ConstraintLayout layoutWebview;
    private SwipeRefreshLayout swipeRefresh;
    private WebView webView;
    private ProgressBar progressBar;
    private TextInputEditText urlInput;
    private Button btnConnect;

    private String serverUrl = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Initialize UI components
        toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        layoutConfig = findViewById(R.id.layout_config);
        layoutWebview = findViewById(R.id.layout_webview);
        swipeRefresh = findViewById(R.id.swipe_refresh);
        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progress_bar);
        urlInput = findViewById(R.id.url_input);
        btnConnect = findViewById(R.id.btn_connect);

        // Configure Swipe Refresh
        swipeRefresh.setOnRefreshListener(() -> {
            if (webView != null && serverUrl != null && !serverUrl.isEmpty()) {
                webView.reload();
            } else {
                swipeRefresh.setRefreshing(false);
            }
        });
        swipeRefresh.setColorSchemeResources(R.color.primary);

        // Configure WebView
        setupWebView();

        // Load saved server URL
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        serverUrl = prefs.getString(KEY_SERVER_URL, "");

        if (!serverUrl.isEmpty()) {
            urlInput.setText(serverUrl);
            connectToServer(serverUrl);
        } else {
            showConfigScreen();
        }

        // Connection button click handler
        btnConnect.setOnClickListener(v -> {
            String inputUrl = urlInput.getText().toString().trim();
            if (inputUrl.isEmpty()) {
                Toast.makeText(MainActivity.this, "Please enter a URL", Toast.LENGTH_SHORT).show();
                return;
            }

            // Ensure url has schema
            if (!inputUrl.startsWith("http://") && !inputUrl.startsWith("https://")) {
                inputUrl = "http://" + inputUrl;
            }

            // Remove trailing slash if exists to normalize
            if (inputUrl.endsWith("/")) {
                inputUrl = inputUrl.substring(0, inputUrl.length() - 1);
            }

            connectToServer(inputUrl);
        });
    }

    private void setupWebView() {
        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setUseWideViewPort(true);
        webSettings.setBuiltInZoomControls(true);
        webSettings.setDisplayZoomControls(false);
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        
        // Cache settings for smooth offline-like operation
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                // Keep URL loading inside the app WebView
                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                
                // Only handle main frame loading errors
                if (request.isForMainFrame()) {
                    progressBar.setVisibility(View.GONE);
                    swipeRefresh.setRefreshing(false);
                    Toast.makeText(MainActivity.this, "Webview Error: " + error.getDescription(), Toast.LENGTH_LONG).show();
                    showConfigScreen();
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                super.onProgressChanged(view, newProgress);
                if (newProgress < 100) {
                    progressBar.setVisibility(View.VISIBLE);
                } else {
                    progressBar.setVisibility(View.GONE);
                }
            }
        });
    }

    private void connectToServer(String targetUrl) {
        if (!isNetworkAvailable()) {
            Toast.makeText(this, "No internet connection available", Toast.LENGTH_SHORT).show();
            return;
        }

        btnConnect.setEnabled(false);
        btnConnect.setText("Testing connection...");
        progressBar.setVisibility(View.VISIBLE);

        new PingServerTask(targetUrl).execute();
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager connectivityManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (connectivityManager != null) {
            NetworkInfo activeNetworkInfo = connectivityManager.getActiveNetworkInfo();
            return activeNetworkInfo != null && activeNetworkInfo.isConnected();
        }
        return false;
    }

    private void showConfigScreen() {
        layoutConfig.setVisibility(View.VISIBLE);
        layoutWebview.setVisibility(View.GONE);
        btnConnect.setEnabled(true);
        btnConnect.setText("Connect & Start App");
    }

    private void showWebViewScreen() {
        layoutConfig.setVisibility(View.GONE);
        layoutWebview.setVisibility(View.VISIBLE);
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_main, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (item.getItemId() == R.id.action_change_server) {
            showConfigScreen();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onBackPressed() {
        if (layoutWebview.getVisibility() == View.VISIBLE && webView.canGoBack()) {
            webView.goBack();
        } else if (layoutWebview.getVisibility() == View.VISIBLE) {
            // If we are at the homepage of webview, let user go back to config screen
            showConfigScreen();
        } else {
            super.onBackPressed();
        }
    }

    // Background task to ping the Flask /api/health endpoint to verify connection
    private class PingServerTask extends AsyncTask<Void, Void, Boolean> {
        private final String testUrl;

        PingServerTask(String url) {
            this.testUrl = url;
        }

        @Override
        protected Boolean doInBackground(Void... voids) {
            HttpURLConnection connection = null;
            try {
                // Ping /api/health to confirm the Flask server is up and responsive
                URL url = new URL(testUrl + "/api/health");
                connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(5000); // 5 seconds
                connection.setReadTimeout(5000);
                connection.connect();

                int responseCode = connection.getResponseCode();
                return responseCode == HttpURLConnection.HTTP_OK;
            } catch (IOException e) {
                e.printStackTrace();
                return false;
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
        }

        @Override
        protected void onPostExecute(Boolean success) {
            progressBar.setVisibility(View.GONE);
            btnConnect.setEnabled(true);
            btnConnect.setText("Connect & Start App");

            if (success) {
                // Save URL in preferences
                serverUrl = testUrl;
                SharedPreferences.Editor editor = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit();
                editor.putString(KEY_SERVER_URL, serverUrl);
                editor.apply();

                // Show webview and load page
                showWebViewScreen();
                webView.loadUrl(serverUrl + "/login.html");
                Toast.makeText(MainActivity.this, "Connected successfully!", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(MainActivity.this, "Connection failed. Please check that your Flask server is running at the specified address.", Toast.LENGTH_LONG).show();
            }
        }
    }
}
