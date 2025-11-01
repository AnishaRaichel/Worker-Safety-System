# run_safety_engine.py
import serial
import joblib
from datetime import datetime, UTC
from awscrt import mqtt
from awsiot import mqtt_connection_builder
import json

# Load fatigue model
model = joblib.load("fatigue_model.pkl")

# Connect to Arduino (update COM port for your system)
ser = serial.Serial("COM6", 115200, timeout=1)

# ---------------- AWS IoT CONFIG ----------------
ENDPOINT = "av9jwzd2rso2p-ats.iot.ap-southeast-2.amazonaws.com"  # replace with your AWS IoT endpoint
CLIENT_ID = "safety_engine_client"
PATH_TO_CERT = "44da401731e5ea18d31242463139301114b9fdfe983ebd0388f3bd67732b692e-certificate.pem.crt"
PATH_TO_KEY = "44da401731e5ea18d31242463139301114b9fdfe983ebd0388f3bd67732b692e-private.pem.key"
PATH_TO_ROOT = "AmazonRootCA1.pem"

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=PATH_TO_CERT,
    pri_key_filepath=PATH_TO_KEY,
    client_id=CLIENT_ID,
    ca_filepath=PATH_TO_ROOT,
    clean_session=False,
    keep_alive_secs=30
)

print("🔗 Connecting to AWS IoT Core...")
mqtt_connection.connect().result()
print("✅ Connected to AWS IoT Core")

# ---------------- PARSE + SAFETY CHECK ----------------
def parse_line(line):
    parts = line.strip().split(',')
    data = {}
    for p in parts:
        if ':' in p:
            k, v = p.split(':', 1)
            try:
                data[k] = float(v)
            except:
                data[k] = v
    return data

def safety_check(data):
    alerts = []

    # Fatigue ML
    X = [[data["HR"], data["SLEEP"], data["STEPS"], data["MOOD"]]]
    pred = model.predict(X)[0]
    if pred == 1:
        alerts.append("Fatigue/Burnout")

    # Heat Hazard
    if data["TEMP"] > 38 or data["HUM"] > 80:
        alerts.append("Heat Hazard")

    # Proximity
    if data["DIST"] < 15:
        alerts.append("Critical Danger Zone")
    elif data["DIST"] < 30:
        alerts.append("Danger Zone")

    # Unauthorized Access
    if data["IR"] == 1:
        alerts.append("Unauthorized Access")

    status = " & ".join(alerts) if alerts else "Safe"

    record = {
        "employee_id": int(data["EMP"]),
        "status": status,
        "timestamp": datetime.now(UTC).isoformat()
    }
    return record

# ---------------- MAIN LOOP ----------------
print("✅ Safety engine running...")

while True:
    line = ser.readline().decode(errors='ignore').strip()
    if line:
        data = parse_line(line)
        if "EMP" in data:
            result = safety_check(data)

            # Print clean output
            print(
                f"[{result['timestamp']}] "
                f"EMP:{data['EMP']} | HR:{data['HR']} | "
                f"SLEEP:{data['SLEEP']} | STEPS:{data['STEPS']} | MOOD:{data['MOOD']} | "
                f"TEMP:{data['TEMP']} | HUM:{data['HUM']} | DIST:{data['DIST']} | IR:{data['IR']} "
                f"--> STATUS: {result['status']}"
            )

            # Send command back to Arduino
            if result["status"] == "Safe":
                ser.write(b"SAFE")
            else:
                ser.write(b"ALERT")

                # ☁️ Publish ALERT to AWS IoT
            message = {
                "employee_id": result["employee_id"],
                "status": result["status"],
                "timestamp": result["timestamp"],
                "HR": data["HR"],
                "TEMP": data["TEMP"],
                "HUM": data["HUM"],
                "SLEEP": data["SLEEP"],
                "STEPS": data["STEPS"],
                "MOOD": data["MOOD"],
                "DIST": data["DIST"],
                "IR": data["IR"]
            }


                
            mqtt_connection.publish(
                    topic="safety/alerts",
                    payload=json.dumps(message),
                    qos=mqtt.QoS.AT_LEAST_ONCE
                )
            print("☁️ Sent alert to AWS:", message)
