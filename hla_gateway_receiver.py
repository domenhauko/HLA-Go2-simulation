#!/usr/bin/env python3

import os
import json
import time
from pathlib import Path

import jpype
import jpype.imports
from jpype import JProxy
import paho.mqtt.client as mqtt
from queue import Queue, Empty

# ----------------------- HLA CONFIG ------------------------
PRTI_HOME = os.environ.get(
    "RTI_HOME",
    "/home/domen/Documents/LAK/portico-2.1.4"
)
LOCAL_SETTINGS = "192.168.0.100:8989"
FEDERATION_NAME = "DemoFederation"
FEDERATE_NAME = "GatewayFederate"
FEDERATE_TYPE = "Gateway"
OBJECT_CLASS_FQN = "HLAobjectRoot.Vehicle"

ATTR_X = "x"
ATTR_Y = "y"
ATTR_YAW = "yaw"

# ----------------------- MQTT CONFIG ------------------------
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "go2/vehicle_state"
MQTT_CLIENT_ID = "HLA_Gateway_Client"


def ensure_jvm():
    if jpype.isJVMStarted():
        return

    jvm_path = "/usr/lib/jvm/java-11-openjdk-amd64/lib/server/libjvm.so"
    portico_jar = os.path.join(PRTI_HOME, "lib", "portico.jar")

    if not os.path.exists(jvm_path):
        raise RuntimeError(f"Linux JVM not found: {jvm_path}")
    if not os.path.exists(portico_jar):
        raise RuntimeError(f"Portico jar not found: {portico_jar}")

    jpype.startJVM(
        jvm_path,
        classpath=[portico_jar],
        convertStrings=False
    )
    print(f"[JVM] Started with {portico_jar}")


def get_fom_modules():
    project_dir = Path(__file__).resolve().parent
    fom_file = project_dir / "VehicleFOM.xml"

    if not fom_file.exists():
        raise RuntimeError(f"FOM file not found: {fom_file}")

    File = jpype.JClass("java.io.File")
    URL = jpype.JClass("java.net.URL")

    return jpype.JArray(URL)([
        File(str(fom_file)).toURI().toURL()
    ])


class DummyAmbassador:
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

    def discoverObjectInstance(self, *args):
        pass

    def reflectAttributeValues(self, *args):
        pass

    def removeObjectInstance(self, *args):
        pass


class HlaPublisher:
    def __init__(self):
        ensure_jvm()

        self.RtiFactoryFactory = jpype.JClass("hla.rti1516e.RtiFactoryFactory")
        self.CallbackModel = jpype.JClass("hla.rti1516e.CallbackModel")
        self.ResignAction = jpype.JClass("hla.rti1516e.ResignAction")

        self.rti_factory = self.RtiFactoryFactory.getRtiFactory()
        self.rtia = self.rti_factory.getRtiAmbassador()
        self.encoder_factory = self.rti_factory.getEncoderFactory()

        self.fedamb_impl = DummyAmbassador()
        self.fedamb = JProxy("hla.rti1516e.FederateAmbassador", inst=self.fedamb_impl)

        self.vehicle_class = None
        self.obj_handle = None
        self.h_x = None
        self.h_y = None
        self.h_yaw = None

        self._connected = False
        self._joined = False

        self._setup_hla()

    def _setup_hla(self):
        modules = get_fom_modules()

        if not self._connected:
            self.rtia.connect(self.fedamb, self.CallbackModel.HLA_EVOKED, LOCAL_SETTINGS)
            self._connected = True
            print("[HLA] Connected to RTI")

        try:
            self.rtia.createFederationExecution(FEDERATION_NAME, modules)
            print(f"[HLA] Created federation: {FEDERATION_NAME}")
        except Exception as e:
            print(f"[HLA] Federation may already exist: {e}")

        if not self._joined:
            self.rtia.joinFederationExecution(
                FEDERATE_NAME,
                FEDERATE_TYPE,
                FEDERATION_NAME,
                modules
            )
            self._joined = True
            print(f"[HLA] Joined federation: {FEDERATION_NAME}")

        self.vehicle_class = self.rtia.getObjectClassHandle(OBJECT_CLASS_FQN)

        self.h_x = self.rtia.getAttributeHandle(self.vehicle_class, ATTR_X)
        self.h_y = self.rtia.getAttributeHandle(self.vehicle_class, ATTR_Y)
        self.h_yaw = self.rtia.getAttributeHandle(self.vehicle_class, ATTR_YAW)

        ahs = self.rtia.getAttributeHandleSetFactory().create()
        ahs.add(self.h_x)
        ahs.add(self.h_y)
        ahs.add(self.h_yaw)

        self.rtia.publishObjectClassAttributes(self.vehicle_class, ahs)
        self.obj_handle = self.rtia.registerObjectInstance(self.vehicle_class)
        print("[HLA] Registered Vehicle object")
        print(f"[HLA] vehicle_class={self.vehicle_class}")
        print(f"[HLA] handle x={self.h_x}, y={self.h_y}, yaw={self.h_yaw}")
        print(f"[HLA] object handle={self.obj_handle}")

    def publish_vehicle_state(self, x: float, y: float, yaw: float):
        if self.obj_handle is None:
            raise RuntimeError("HLA object handle is not initialized")

        ahvm = self.rtia.getAttributeHandleValueMapFactory().create(3)

        enc = self.encoder_factory.createHLAfloat64BE()

        enc.setValue(float(x))
        ahvm.put(self.h_x, enc.toByteArray())

        enc.setValue(float(y))
        ahvm.put(self.h_y, enc.toByteArray())

        enc.setValue(float(yaw))
        ahvm.put(self.h_yaw, enc.toByteArray())

        self.rtia.updateAttributeValues(self.obj_handle, ahvm, b"gateway")
        self.rtia.evokeMultipleCallbacks(0.001, 0.01)

    def shutdown(self):
        try:
            if self._joined:
                self.rtia.resignFederationExecution(self.ResignAction.NO_ACTION)
                print("[HLA] Resigned federation")
        except Exception as e:
            print(f"[HLA] Resign skipped: {e}")


class MqttReceiver:
    def __init__(self, broker: str, port: int, topic: str, client_id: str) -> None:
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id
        self.client = mqtt.Client(client_id=self.client_id)

        self.hla = HlaPublisher()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()

        self.state_queue = Queue()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to {self.broker}:{self.port} successfully.")
            self.client.subscribe(self.topic, qos=1)
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)
            self.process_vehicle_state(data)
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def process_vehicle_state(self, data: dict):
        try:
            robot_id = data.get("robot_id", "N/A")
            seq = data.get("seq", -1)
            x = data.get("x", 0.0)
            y = data.get("y", 0.0)
            yaw = data.get("yaw", 0.0)
            v_linear = data.get("v_linear", 0.0)
            v_angular = data.get("v_angular", 0.0)

            print(
                f"[Received VehicleState] seq={seq}, robot_id={robot_id}, "
                f"x={x}, y={y}, yaw={yaw}, v_linear={v_linear}, v_angular={v_angular}"
            )

            self.state_queue.put((seq, x, y, yaw))

        except Exception as e:
            print(f"Error processing VehicleState: {e}")

    def send_to_hla(self, seq: int, x: float, y: float, yaw: float):
        try:
            self.hla.publish_vehicle_state(x, y, yaw)
            print(f"[HLA Sent] seq={seq} | x={x}, y={y}, yaw={yaw}")
        except Exception as e:
            print(f"Error sending data to HLA: {e}")

    def shutdown(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

        try:
            self.hla.shutdown()
        except Exception:
            pass


def main():
    print(f"[DEBUG] PRTI_HOME={PRTI_HOME}")
    mqtt_receiver = MqttReceiver(MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_CLIENT_ID)

    try:
        while True:
            try:
                seq, x, y, yaw = mqtt_receiver.state_queue.get(timeout=0.1)
                mqtt_receiver.send_to_hla(seq, x, y, yaw)
            except Empty:
                pass

            try:
                mqtt_receiver.hla.rtia.evokeMultipleCallbacks(0.001, 0.01)
            except Exception:
                pass

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        mqtt_receiver.shutdown()


if __name__ == "__main__":
    main()