# QueueWise – Intelligent Queue Prediction and Crowd Flow Management System

A local Streamlit application for token generation, queue tracking, counter management and queue analytics.

## Features
- Generate a unique daily token for a customer/student.
- Normal and priority queue ordering.
- Live queue view with estimated waiting time.
- Admin controls to activate/deactivate counters, call tokens and complete service.
- Average service-time calculation based on completed services.
- Analytics charts and CSV exports.
- SQLite storage so records persist between application restarts.

## Requirements
- Python 3.9 or newer

## Run on Windows
Open Command Prompt in this folder and run:

```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Open the local URL shown in the terminal (normally http://localhost:8501).

## Demo admin PIN
`1234`

Change this before any real deployment. The demo PIN is not secure authentication.

## Database
The app automatically creates `data/queuewise.db` on first launch. Keep this file if you want to retain local records. To reset demo data, stop Streamlit and delete the database file.

## Waiting-time estimate
The application estimates waiting time using the customer's position in the waiting queue, the number of active counters, and the average duration of recently completed services. Until service history exists, it uses a five-minute starting estimate. This is a simple operational estimate, not a trained machine-learning model.

## Limitations
- Local single-machine demonstration; no cloud hosting or multi-user synchronisation.
- Admin PIN is a demo gate, not production-grade authentication.
- No QR code scanning or SMS/WhatsApp notifications in this version.
- Priority handling depends on authorised staff and must be used fairly.
