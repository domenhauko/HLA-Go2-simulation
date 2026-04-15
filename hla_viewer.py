#!/usr/bin/env python3

import jpype
import jpype.imports
from jpype import JProxy
import matplotlib.pyplot as plt
import math

# ---------------- HLA CONFIG ------------------------
PRTI_HOME = r"C:\Program Files\portico-2.1.3"
JVM_DLL = r"C:\Program Files\portico-2.1.3\jre\bin\server\jvm.dll"
LOCAL_SETTINGS = "127.0.0.1:8989"
FEDERATION_NAME = "DemoFederation"
FEDERATE_NAME = "ViewerFederate"
FEDERATE_TYPE = "Viewer"
OBJECT_CLASS_FQN = "HLAobjectRoot.Vehicle"

# ---------------- HLA CALLBACKS ----------------------
class ViewerAmbassador:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

    def reflectAttributeValues(self, theObject, theAttributes, tag, orderType, transportationType, supplementalInfo):
        """Callback for attribute values (x, y, yaw) updates"""
        vals = {}
        for attr_handle in list(theAttributes.keySet()):
            raw_value = theAttributes.get(attr_handle)
            name = self.handle_to_name.get(attr_handle, None)
            if name:
                vals[name] = raw_value
        if "x" in vals and "y" in vals and "yaw" in vals:
            self.x = vals["x"]
            self.y = vals["y"]
            self.yaw = vals["yaw"]

    def synchronizationPointRegistrationSucceeded(self, label):
        pass

    def synchronizationPointRegistrationFailed(self, label, reason):
        pass

    def announceSynchronizationPoint(self, label, tag):
        pass

    def federationSynchronized(self, label, failedToSyncSet):
        pass

# --------------- HLA RTI INTERFACE -------------------
def ensure_jvm():
    """Ensure JVM is started for HLA operations."""
    if jpype.isJVMStarted():
        return

    # Update the JVM path for Linux
    jvm_path = "/usr/lib/jvm/java-11-openjdk-amd64/lib/server/libjvm.so"  # Adjust this path if needed

    jpype.startJVM(
        jvm_path,
        classpath=[
            f"{PRTI_HOME}/lib/prti1516e.jar",
            f"{PRTI_HOME}/lib/hla1516e.jar"
        ]
    )
    print("[JVM] Started")

def setup_hla_listener():
    """Sets up the HLA listener to receive robot state updates."""
    ensure_jvm()

    # RTI setup
    RtiFactoryFactory = jpype.JClass("hla.rti1516e.RtiFactoryFactory")
    CallbackModel = jpype.JClass("hla.rti1516e.CallbackModel")
    rti_factory = RtiFactoryFactory.getRtiFactory()
    rtia = rti_factory.getRtiAmbassador()
    encoder_factory = rti_factory.getEncoderFactory()

    viewer_ambassador = ViewerAmbassador()
    fedamb = JProxy("hla.rti1516e.FederateAmbassador", inst=viewer_ambassador)

    # Connect to RTI
    rtia.connect(fedamb, CallbackModel.HLA_EVOKED, LOCAL_SETTINGS)
    rtia.joinFederationExecution(FEDERATE_NAME, FEDERATE_TYPE, FEDERATION_NAME)

    # Subscribe to the Vehicle object class and its attributes
    vehicle_class = rtia.getObjectClassHandle(OBJECT_CLASS_FQN)
    attr_handles = [
        rtia.getAttributeHandle(vehicle_class, "x"),
        rtia.getAttributeHandle(vehicle_class, "y"),
        rtia.getAttributeHandle(vehicle_class, "yaw"),
    ]
    rtia.subscribeObjectClassAttributes(vehicle_class, attr_handles)

    return viewer_ambassador


# --------------- Visualization -------------------
def plot_robot_state(viewer_ambassador):
    """Visualize robot position and orientation using matplotlib."""
    plt.ion()
    fig, ax = plt.subplots()
    ax.set_aspect('equal', adjustable='box')
    ax.set_title("Robot Position in HLA Federation")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True)

    robot_body, = ax.plot([], [], marker="o", color="blue", label="Robot")
    robot_heading, = ax.plot([], [], color="orange", linewidth=2, label="Heading")
    ax.legend(loc="upper right")

    while True:
        # Get the latest robot state
        x, y, yaw = viewer_ambassador.x, viewer_ambassador.y, viewer_ambassador.yaw

        # Update the robot's position and heading
        robot_body.set_data(x, y)
        x1 = x + 0.5 * math.cos(yaw)
        y1 = y + 0.5 * math.sin(yaw)
        robot_heading.set_data([x, x1], [y, y1])

        fig.canvas.draw_idle()
        fig.canvas.flush_events()

        plt.pause(0.1)

# --------------- Main Function -------------------
def main():
    viewer_ambassador = setup_hla_listener()
    plot_robot_state(viewer_ambassador)

if __name__ == "__main__":
    main()