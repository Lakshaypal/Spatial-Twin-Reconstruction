import paho.mqtt.client as mqtt
import time
import random
import json

BROKER = "127.0.0.1"
PORT = 1883
TOPIC = "sensor/dht11"

def main():
    print("Starting Arduino IoT Simulator...")
    print(f"Connecting to MQTT broker at {BROKER}:{PORT}")
    
    client = mqtt.Client()
    try:
        client.connect(BROKER, PORT, 60)
    except ConnectionRefusedError:
        print("ERROR: Connection refused. Is Mosquitto running?")
        print("Please install and run mosquitto (e.g., 'mosquitto -v' in terminal)")
        return

    print("Connected! Simulating DHT11 sensor data...")
    print("Press Ctrl+C to stop.")
    
    temp = 22.0
    humidity = 45.0
    
    try:
        while True:
            # Simulate slight changes in environment
            temp += random.uniform(-0.5, 0.5)
            humidity += random.uniform(-1.0, 1.0)
            
            # Format payload
            payload = {
                "temperature_c": round(temp, 1),
                "humidity": round(humidity, 1)
            }
            
            msg = f"Temp: {payload['temperature_c']}°C | Hum: {payload['humidity']}%"
            client.publish(TOPIC, msg)
            
            print(f"Published to {TOPIC}: {msg}")
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        client.disconnect()

if __name__ == "__main__":
    main()
