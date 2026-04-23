#!/usr/bin/env python3
import os
import math
import jpype
import jpype.imports
from jpype import JProxy
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

PRTI_HOME = os.environ.get(
    "RTI_HOME",
    "/home/domen/Documents/LAK/portico-2.1.4"
)

LOCAL_SETTINGS = "127.0.0.1:8989"
FEDERATION_NAME = "DemoFederation"
FEDERATE_NAME = "ViewerFederate"
FEDERATE_TYPE = "Viewer"
OBJECT_CLASS_FQN = "HLAobjectRoot.Vehicle"

ATTR_X = "x"
ATTR_Y = "y"
ATTR_YAW = "yaw"


def ensure_jvm():
    if jpype.isJVMStarted():
        return

    jvm_path = "/usr/lib/jvm/java-11-openjdk-amd64/lib/server/libjvm.so"
    portico_jar = os.path.join(PRTI_HOME, "lib", "portico.jar")

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


class ViewerAmbassador:
    def __init__(self, encoder_factory):
        self.dec = encoder_factory.createHLAfloat64BE()
        self.handle_to_name = {}
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.has_data = False

    def _decode(self, raw):
        self.dec.decode(raw)
        return float(self.dec.getValue())

    def discoverObjectInstance(self, theObject, theObjectClass, objectName):
        print(f"[HLA DISCOVER] object={theObject}, class={theObjectClass}, name={objectName}")

    def reflectAttributeValues(self, *args):
        try:
            if len(args) < 2:
                return

            the_attributes = args[1]
            print(f"[HLA RAW UPDATE] attribute count={the_attributes.size()}")

            vals = {}

            for h in list(the_attributes.keySet()):
                key = str(h)
                name = self.handle_to_name.get(key)
                print(f"[HLA HANDLE] raw={h} key={key} mapped={name}")

                if name is not None:
                    vals[name] = the_attributes.get(h)

            updated = False

            if ATTR_X in vals:
                self.x = self._decode(vals[ATTR_X])
                updated = True
            if ATTR_Y in vals:
                self.y = self._decode(vals[ATTR_Y])
                updated = True
            if ATTR_YAW in vals:
                self.yaw = self._decode(vals[ATTR_YAW])
                updated = True

            if updated:
                self.has_data = True
                print(f"[HLA UPDATE] x={self.x:.3f}, y={self.y:.3f}, yaw={self.yaw:.3f}")

        except Exception as e:
            print("[VIEWER ERROR] reflectAttributeValues:", e)

    def synchronizationPointRegistrationSucceeded(self, label):
        pass

    def synchronizationPointRegistrationFailed(self, label, reason):
        pass

    def announceSynchronizationPoint(self, label, tag):
        pass

    def federationSynchronized(self, label, failedToSyncSet):
        pass

    def timeAdvanceGrant(self, theTime):
        pass

    def receiveInteraction(self, *args):
        pass

    def removeObjectInstance(self, *args):
        pass


def main():
    ensure_jvm()

    RtiFactoryFactory = jpype.JClass("hla.rti1516e.RtiFactoryFactory")
    CallbackModel = jpype.JClass("hla.rti1516e.CallbackModel")
    ResignAction = jpype.JClass("hla.rti1516e.ResignAction")

    rti_factory = RtiFactoryFactory.getRtiFactory()
    rtia = rti_factory.getRtiAmbassador()
    encoder_factory = rti_factory.getEncoderFactory()

    amb_obj = ViewerAmbassador(encoder_factory)
    fedamb = JProxy("hla.rti1516e.FederateAmbassador", inst=amb_obj)

    rtia.connect(fedamb, CallbackModel.HLA_EVOKED, LOCAL_SETTINGS)

    modules = get_fom_modules()

    try:
        rtia.createFederationExecution(FEDERATION_NAME, modules)
        print(f"[HLA] Created federation: {FEDERATION_NAME}")
    except Exception as e:
        print(f"[HLA] Federation may already exist: {e}")

    rtia.joinFederationExecution(
        FEDERATE_NAME,
        FEDERATE_TYPE,
        FEDERATION_NAME,
        modules
    )
    print(f"[HLA] Joined federation: {FEDERATION_NAME}")

    vehicle_class = rtia.getObjectClassHandle(OBJECT_CLASS_FQN)
    h_x = rtia.getAttributeHandle(vehicle_class, ATTR_X)
    h_y = rtia.getAttributeHandle(vehicle_class, ATTR_Y)
    h_yaw = rtia.getAttributeHandle(vehicle_class, ATTR_YAW)

    ahs = rtia.getAttributeHandleSetFactory().create()
    ahs.add(h_x)
    ahs.add(h_y)
    ahs.add(h_yaw)
    rtia.subscribeObjectClassAttributes(vehicle_class, ahs)

    amb_obj.handle_to_name = {
        str(h_x): ATTR_X,
        str(h_y): ATTR_Y,
        str(h_yaw): ATTR_YAW,
    }
    print("[HLA SUBSCRIBED HANDLES]", amb_obj.handle_to_name)

    plt.ion()
    fig, ax = plt.subplots()
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True)
    ax.set_title("HLA Viewer")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)

    robot_length = 0.7
    robot_width = 0.4
    arrow_length = 0.6

    robot_body = Rectangle(
        (-robot_length / 2, -robot_width / 2),
        robot_length,
        robot_width,
        angle=0.0,
        fill=False,
        edgecolor="blue",
        linewidth=2
    )
    ax.add_patch(robot_body)

    heading_line, = ax.plot([], [], color="orange", linewidth=3)

    def update_robot_patch(x, y, yaw):
        yaw_deg = math.degrees(yaw)

        dx = -robot_length / 2
        dy = -robot_width / 2

        cos_y = math.cos(yaw)
        sin_y = math.sin(yaw)

        llx = x + dx * cos_y - dy * sin_y
        lly = y + dx * sin_y + dy * cos_y

        robot_body.set_xy((llx, lly))
        robot_body.angle = yaw_deg

        hx = x + arrow_length * cos_y
        hy = y + arrow_length * sin_y
        heading_line.set_data([x, hx], [y, hy])

        margin = 2.0
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()

        if x < xmin + 1 or x > xmax - 1 or y < ymin + 1 or y > ymax - 1:
            ax.set_xlim(x - margin, x + margin)
            ax.set_ylim(y - margin, y + margin)

    update_robot_patch(0.0, 0.0, 0.0)
    fig.canvas.draw_idle()
    fig.canvas.flush_events()

    loop_counter = 0

    try:
        while True:
            rtia.evokeMultipleCallbacks(0.001, 0.01)
            loop_counter += 1

            if loop_counter % 100 == 0:
                print(f"[VIEW LOOP] has_data={amb_obj.has_data}")

            if amb_obj.has_data:
                x, y, yaw = amb_obj.x, amb_obj.y, amb_obj.yaw
                update_robot_patch(x, y, yaw)
            else:
                update_robot_patch(0.0, 0.0, 0.0)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(0.01)

    except KeyboardInterrupt:
        print("\n[HLA] Viewer stopped by user")

    finally:
        try:
            rtia.resignFederationExecution(ResignAction.NO_ACTION)
            print("[HLA] Resigned federation")
        except Exception as e:
            print(f"[HLA] Resign skipped: {e}")


if __name__ == "__main__":
    main()