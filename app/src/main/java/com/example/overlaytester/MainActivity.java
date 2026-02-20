package com.example.overlaytester;

import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private boolean running = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        TextView status = findViewById(R.id.statusText);
        Button start = findViewById(R.id.startButton);
        Button stop = findViewById(R.id.stopButton);

        start.setOnClickListener(v -> {
            running = true;
            status.setText(getString(R.string.status_running));
        });

        stop.setOnClickListener(v -> {
            running = false;
            status.setText(getString(R.string.status_stopped));
        });

        status.setText(running ? getString(R.string.status_running) : getString(R.string.status_stopped));
    }
}
