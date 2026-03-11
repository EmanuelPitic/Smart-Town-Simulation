# Smart Town IoT Simulation & Custom MQTT v5 Broker

## About the Project
This project is a comprehensive cyber-physical system that simulates a smart town environment. At its core is a custom-built MQTT v5 broker that facilitates real-time, asynchronous communication between various IoT devices, including an autonomous vehicle and an intelligent traffic light system. 

The architecture bridges the gap between hardware and software, demonstrating how low-level microcontroller programming, network protocols, and web interfaces come together to create a reliable distributed system.

### Key Features
* **Custom MQTT v5 Broker:** Engineered from scratch in Python using raw socket programming. It handles packet decoding, QoS mechanisms, and includes a SQLite database for state management alongside a web-based GUI for network monitoring.
* **Autonomous Vehicle:** Powered by a Raspberry Pi Pico W. It utilizes dual-core processing for IR line-tracking, HC-SR04 ultrasonic sensors for obstacle and traffic light detection, and operates via state-machine logic (manual, autonomous, or emergency modes).
* **Intelligent Traffic Light System:** Controlled by a Raspberry Pi Pico W. It uses IR sensors to detect waiting vehicles and dynamically adjusts green-light cycles to optimize traffic flow. It supports manual, sequential, and intelligent modes, with a Bluetooth (HC-05) fallback for local control.

---

## Table of Contents
### Chapter 1: Car
#### Subchapter 1
* [1. Introduction](/Documentation/Car/Chapter%201/1.Introduction.md)
* [2. Components Description](/Documentation/Car/Chapter%201/2.Components%20Description.md)
#### Subchapter 2
* [1. Electronic Components](/Documentation/Car/Chapter%202/1.Electronic%20Components.md)
* [2. Chassis](/Documentation/Car/Chapter%202/2.Chassis.md)
* [3. Connecting Components](/Documentation/Car/Chapter%202/3.Connecting%20Components.md)
#### Subchapter 3
* [1. Operating Mode](/Documentation/Car/Chapter%203/1.%20Operating%20Mode.md)
* [2. Application Design](/Documentation/Car/Chapter%203/2.Application%20Design.md)
* [3. Server Connection](/Documentation/Car/Chapter%203/3.Server%20Connection.md)

### Chapter 2: Traffic Light
#### Subchapter 1
* [1. Introduction](/Documentation/Traffic%20Light/Chapter%201/1.Introduction.md)
* [2. Components Description](/Documentation/Traffic%20Light/Chapter%201/2.Components%20Description.md)
#### Subchapter 2
* [1. Operating Mode](/Documentation/Traffic%20Light/Chapter%202/1.Operating%20Mode.md)
* [2. Application Design](/Documentation/Traffic%20Light/Chapter%202/2.Application%20Design.md)
* [3. Connecting Components](/Documentation/Traffic%20Light/Chapter%202/3.Connecting_Components.md)
* [4. Server Connection](/Documentation/Traffic%20Light/Chapter%202/4.Server%20Connection.md)

### Chapter 3: Server
#### Subchapter 1
* [1. Introduction](/Documentation/Server/Chapter%201/1.Introduction.md)
* [2. Theoretical Aspects](/Documentation/Server/Chapter%201/2.Theoretical%20Aspects.md)
* [3. PublishAndSubscribe](/Documentation/Server/Chapter%201/3.PublishAndSubscribe.md)
* [4. Broker](/Documentation/Server/Chapter%201/4.Broker.md)
* [5. MQTT Mechanisms](/Documentation/Server/Chapter%201/5.MQTT%20Mechanisms.md)
#### Subchapter 2
* [1. Implementation](/Documentation/Server/Chapter%202/1.Implementation.md)
* [2. Bibliography](/Documentation/Server/Chapter%202/2.Bibliography.md)
#### Other Sections
* [Demo](/Documentation/Demo.md)

---

## Authors
This project was realised by:
- Aeloaiei Denisa-Valentina
- Agavriloaei Marina
- Bîrleanu Andreea
- Pitic Emanuel
- Stroici Andrei
- Voicu Gabriel