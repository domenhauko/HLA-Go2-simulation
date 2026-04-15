#!/usr/bin/env python3

import json
import paho.mqtt.client as mqtt
import time


class MqttReceiver:
    def __init__(self, broker: str, port: int, topic: str, client_id: str) -> None:
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id
        self.client = mqtt.Client(client_id=self.client_id)

        # MQTT Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            print(f"Connected to {self.broker}:{self.port} successfully.")
            self.client.subscribe(self.topic, qos=1)
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")

    def on_message(self, client, userdata, msg):
        """Message handler for receiving and parsing JSON"""
        try:
            # Decode the incoming message payload
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)

            # Validate and print the received VehicleState
            self.print_vehicle_state(data)

        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def print_vehicle_state(self, data: dict):
        """Print the parsed VehicleState"""
        try:
            robot_id = data.get("robot_id", "N/A")
            seq = data.get("seq", -1)
            timestamp_ns = data.get("timestamp_ns", -1)
            publish_time_ns = data.get("publish_time_ns", -1)
            x = data.get("x", 0.0)
            y = data.get("y", 0.0)
            yaw = data.get("yaw", 0.0)
            v_linear = data.get("v_linear", 0.0)
            v_angular = data.get("v_angular", 0.0)

            print(f"[VehicleState] seq={seq} robot_id={robot_id} | "
                  f"timestamp_ns={timestamp_ns} publish_time_ns={publish_time_ns} | "
                  f"x={x} y={y} yaw={yaw} | "
                  f"v_linear={v_linear} v_angular={v_angular}")
        except Exception as e:
            print(f"Error printing VehicleState: {e}")

    def run(self):
        """Start the MQTT listener loop"""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
            self.client.loop_stop()


if __name__ == "__main__":
    # Define the MQTT broker and topic details (same as in the adapter)
    mqtt_broker = "127.0.0.1"  # Change this if using a different broker IP
    mqtt_port = 1883
    mqtt_topic = "go2/vehicle_state"
    client_id = "mqtt_gateway_receiver"

    # Initialize and run the MQTT receiver
    receiver = MqttReceiver(mqtt_broker, mqtt_port, mqtt_topic, client_id)
    receiver.run()