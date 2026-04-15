#!/usr/bin/env python3

import json
import time
import jpype
import jpype.imports
from jpype import JProxy

import paho.mqtt.client as mqtt

# ----------------------- HLA CONFIG ------------------------
PRTI_HOME = r"C:\Program Files\portico-2.1.3"
JVM_DLL = r"C:\Program Files\portico-2.1.3\jre\bin\server\jvm.dll"
LOCAL_SETTINGS = "127.0.0.1:8989"
FEDERATION_NAME = "DemoFederation"
FEDERATE_NAME = "GatewayFederate"
FEDERATE_TYPE = "Gateway"
OBJECT_CLASS_FQN = "HLAobjectRoot.Vehicle"

# ----------------------- MQTT CONFIG ------------------------
MQTT_BROKER = "127.0.0.1"  # Same as the sender broker
MQTT_PORT = 1883
MQTT_TOPIC = "go2/vehicle_state"
MQTT_CLIENT_ID = "HLA_Gateway_Client"

# ----------------------- MQTT RECEIVER ----------------------
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
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)

            # Validate and process the VehicleState
            self.process_vehicle_state(data)

        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def process_vehicle_state(self, data: dict):
        """Map VehicleState to HLA attributes and send"""
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

            print(f"[Received VehicleState] seq={seq}, robot_id={robot_id}, "
                  f"x={x}, y={y}, yaw={yaw}, v_linear={v_linear}, v_angular={v_angular}")

            # Send data to HLA federation
            self.send_to_hla(seq, robot_id, timestamp_ns, publish_time_ns, x, y, yaw, v_linear, v_angular)

        except Exception as e:
            print(f"Error processing VehicleState: {e}")

    def send_to_hla(self, seq, robot_id, timestamp_ns, publish_time_ns, x, y, yaw, v_linear, v_angular):
        """Send the VehicleState data to the HLA federation"""
        try:
            # Ensure JVM is started
            ensure_jvm()

            # Create the HLA object with attributes
            RtiFactoryFactory = jpype.JClass("hla.rti1516e.RtiFactoryFactory")
            rti_factory = RtiFactoryFactory.getRtiFactory()
            rtia = rti_factory.getRtiAmbassador()
            encoder_factory = rti_factory.getEncoderFactory()

            fedamb_impl = DummyAmbassador()
            fedamb = JProxy("hla.rti1516e.FederateAmbassador", inst=fedamb_impl)

            # Connect to the RTI
            rtia.connect(fedamb, jpype.JClass("hla.rti1516e.CallbackModel").HLA_EVOKED, LOCAL_SETTINGS)
            rtia.joinFederationExecution(FEDERATE_NAME, FEDERATE_TYPE, FEDERATION_NAME)

            # Get the object class handle
            vehicle_class = rtia.getObjectClassHandle(OBJECT_CLASS_FQN)

            # Set up HLA object attribute handles (map fields to HLA attributes)
            h_id = rtia.getAttributeHandle(vehicle_class, "id")
            h_x = rtia.getAttributeHandle(vehicle_class, "x")
            h_y = rtia.getAttributeHandle(vehicle_class, "y")
            h_yaw = rtia.getAttributeHandle(vehicle_class, "yaw")
            h_v_linear = rtia.getAttributeHandle(vehicle_class, "v_linear")
            h_v_angular = rtia.getAttributeHandle(vehicle_class, "v_angular")

            # Update the object instance with new attribute values
            obj_handle = rtia.registerObjectInstance(vehicle_class)

            # Prepare parameter map
            phvm = rtia.getParameterHandleValueMapFactory().create(6)
            enc = encoder_factory.createHLAunicodeString()
            enc.setValue(str(robot_id))  # Robot ID
            phvm.put(h_id, enc.toByteArray())

            enc = encoder_factory.createHLAfloat64BE()
            enc.setValue(x)  # Position X
            phvm.put(h_x, enc.toByteArray())

            enc.setValue(y)  # Position Y
            phvm.put(h_y, enc.toByteArray())

            enc.setValue(yaw)  # Yaw angle
            phvm.put(h_yaw, enc.toByteArray())

            enc.setValue(v_linear)  # Linear velocity
            phvm.put(h_v_linear, enc.toByteArray())

            enc.setValue(v_angular)  # Angular velocity
            phvm.put(h_v_angular, enc.toByteArray())

            # Send the update to the RTI
            rtia.updateAttributeValues(obj_handle, phvm, b"gateway")

            print(f"[HLA Sent] seq={seq} robot_id={robot_id} | x={x}, y={y}, yaw={yaw}, "
                  f"v_linear={v_linear}, v_angular={v_angular}")

        except Exception as e:
            print(f"Error sending data to HLA: {e}")


class DummyAmbassador:
    """Dummy HLA ambassador implementation."""
    def synchronizationPointRegistrationSucceeded(self, label):
        pass

    def synchronizationPointRegistrationFailed(self, label, reason):
        pass

    def announceSynchronizationPoint(self, label, tag):
        pass

    def federationSynchronized(self, label, failedToSyncSet):
        pass

    def receiveInteraction(self, *args):
        pass


def ensure_jvm():
    """Ensure JVM is started for HLA operations."""
    if jpype.isJVMStarted():
        return

    jpype.startJVM(
        JVM_DLL,
        classpath=[
            f"{PRTI_HOME}/lib/prti1516e.jar",
            f"{PRTI_HOME}/lib/hla1516e.jar"
        ]
    )


def main():
    mqtt_receiver = MqttReceiver(MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_CLIENT_ID)

    # Start the MQTT loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        mqtt_receiver.client.loop_stop()


if __name__ == "__main__":
    main()