# HLA-Go2-simulation
In this repository it is implemented a Gazebo and ROS2 based simulation for the Unitree Go2 robot as well as a MQTT gateway to a HLA simulation. HLA is implemented with Portico RTI.

## Resources
This project is based on a github repo https://github.com/anujjain-dev/unitree-go2-ros2 and uses Portico https://github.com/openlvc/portico

## Setup
This setup uses Ubuntu 22.04 and Gazebo version 11.10.2 and ROS2 Huumble. THe Anujjain repo is specifically written for this combination so unfortunatelly it doesn't work with other ROS2 versions.
(To check your versions: 
Ubuntu: lsb_release -a
Gazebo: gazebo --version
ROS: $echo ROS_DISTRO)

## Pipeline
GAZEBO simulation of Unitree Go2 robot and teleoperation -> MQTT adapter and receveiver for /odom topic -> HLA viewer
