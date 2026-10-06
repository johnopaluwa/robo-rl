#!/usr/bin/env python3
"""Lifetime test for RosTransport: subscriptions must stay referenced.

This exists because of a real bug that only reproduced on a real ROS 2 box, in
CI, and produced a maddening symptom set:

    ros2 topic hz /detected_object   -> average rate: 5.000     (DDS was fine)
    ros2 node list                   -> /fake_camera /picker /web_viewer
    ros2 topic info                  -> Subscription count: 1   (only the picker)
    the web viewer                   -> received nothing, forever

Cause: rclpy's ``create_subscription()`` returns an object that nothing keeps
alive on your behalf. The transport stored publishers in a dict but discarded
the subscription's return value, so Python's garbage collector tore down the DDS
subscription while the node itself stayed in the graph.

The test below stubs ``rclpy`` and ``std_msgs`` so that the object-lifetime rule
is checked in milliseconds, without a ROS 2 installation -- the point being that
this class of bug should be catchable in the sandbox that cannot run ROS 2.

    python3 -m unittest discover -s tools -p 'test_*.py' -v
"""

from __future__ import annotations

import gc
import os
import sys
import types
import unittest
import weakref

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
WEB_DIR = os.path.join(REPO_ROOT, "web")
for path in (WEB_DIR, REPO_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


class _StubMessage:
    def __init__(self) -> None:
        self.data = ""


class _StubString(_StubMessage):
    pass


class _StubSubscription:
    """Stand-in for rclpy's Subscription, mirroring its free-threading contract."""

    def __init__(self, topic: str, callback) -> None:
        self.topic = topic
        self.callback = callback
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class _StubPublisher:
    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.sent: list[str] = []

    on_publish = None

    def publish(self, message) -> None:
        self.sent.append(message.data)
        if self.on_publish is not None:
            self.on_publish(self.topic, message.data)

    def destroy(self) -> None:
        pass


class _StubNode:
    """Delivery is immediate and in-process, so a self-test cannot pass vacuously."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.subscriptions: list[_StubSubscription] = []
        self.publishers: list[_StubPublisher] = []
        self.deliver = True  # flip to False to simulate a deaf DDS stack

    def create_subscription(self, msg_type, topic, callback, qos):  # noqa: ANN001
        subscription = _StubSubscription(topic, callback)
        self.subscriptions.append(subscription)
        return subscription

    def create_publisher(self, msg_type, topic, qos):  # noqa: ANN001
        publisher = _StubPublisher(topic)
        publisher.on_publish = self._deliver
        self.publishers.append(publisher)
        return publisher

    def _deliver(self, topic: str, payload: str) -> None:
        if not self.deliver:
            return
        for subscription in list(self.subscriptions):
            if subscription.topic == topic:
                message = _StubString()
                message.data = payload
                subscription.callback(message)

    def get_node_names(self):
        return [self.name]

    def get_topic_names_and_types(self):
        return [(publisher.topic, ["std_msgs/msg/String"]) for publisher in self.publishers]

    def destroy_node(self) -> None:
        pass


def _install_stub_ros() -> types.ModuleType:
    """Put fake rclpy / std_msgs modules in sys.modules for the import."""
    rclpy = types.ModuleType("rclpy")
    rclpy.init = lambda args=None: None
    rclpy.ok = lambda: True
    rclpy.shutdown = lambda: None
    rclpy.spin = lambda node: None

    node_module = types.ModuleType("rclpy.node")
    node_module.Node = _StubNode
    rclpy.node = node_module

    msg_module = types.ModuleType("std_msgs.msg")
    msg_module.String = _StubString
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = msg_module

    sys.modules["rclpy"] = rclpy
    sys.modules["rclpy.node"] = node_module
    sys.modules["std_msgs"] = std_msgs
    sys.modules["std_msgs.msg"] = msg_module
    return rclpy


class RosTransportLifetimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            name: sys.modules.get(name)
            for name in ("rclpy", "rclpy.node", "std_msgs", "std_msgs.msg", "transports")
        }
        _install_stub_ros()
        sys.modules.pop("transports", None)  # force a fresh import with the stub
        import transports  # noqa: PLC0415

        self.transports = transports

    def tearDown(self) -> None:
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        sys.modules.pop("transports", None)

    def test_subscription_survives_garbage_collection(self):
        transport = self.transports.build_transport("ros2")
        received: list[str] = []
        transport.subscribe("detected_object", received.append)

        self.assertEqual(len(transport._subscription_objects), 1)
        reference = weakref.ref(transport._subscription_objects[0])

        gc.collect()

        self.assertIsNotNone(
            reference(),
            "the subscription was garbage-collected: rclpy does not keep it alive "
            "for you, so the transport must hold a reference",
        )
        self.assertFalse(transport._subscription_objects[0].destroyed)

    def test_callback_reaches_the_subscriber_after_collection(self):
        transport = self.transports.build_transport("ros2")
        received: list[str] = []
        transport.subscribe("detected_object", received.append)
        gc.collect()

        node = transport.node
        self.assertEqual(len(node.subscriptions), 1)
        message = _StubString()
        message.data = '{"id": 1}'
        node.subscriptions[0].callback(message)  # simulate DDS delivery

        self.assertEqual(received, ['{"id": 1}'])

    def test_subscribing_twice_reuses_one_ros_subscription(self):
        transport = self.transports.build_transport("ros2")
        transport.subscribe("detected_object", lambda _: None)
        transport.subscribe("detected_object", lambda _: None)

        self.assertEqual(len(transport._subscription_objects), 1)
        self.assertEqual(len(transport.node.subscriptions), 1)
        self.assertEqual(len(transport._subscriptions["detected_object"]), 2)

    def test_publishers_are_retained_too(self):
        transport = self.transports.build_transport("ros2")
        transport.publish("arm_command", '{"action": "stop"}')

        self.assertIn("arm_command", transport._publishers)
        self.assertEqual(transport.node.publishers[0].sent, ['{"action": "stop"}'])


class TransportSelftestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            name: sys.modules.get(name)
            for name in ("rclpy", "rclpy.node", "std_msgs", "std_msgs.msg", "transports")
        }
        _install_stub_ros()
        sys.modules.pop("transports", None)
        import transports  # noqa: PLC0415

        self.transports = transports

    def tearDown(self) -> None:
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        sys.modules.pop("transports", None)

    def test_selftest_reports_success_when_the_stack_works(self):
        transport = self.transports.build_transport("ros2")
        transport.start()
        result = transport.selftest(timeout_s=1.0)
        self.assertTrue(result["sent"])
        self.assertTrue(
            result["received"],
            "the loopback self-test must report success when delivery works",
        )

    def test_selftest_reports_failure_when_messages_never_arrive(self):
        """The decisive case: this is what a broken DDS stack looks like."""
        transport = self.transports.build_transport("ros2")
        transport.node.deliver = False
        transport.start()
        result = transport.selftest(timeout_s=0.3)
        self.assertTrue(result["sent"])
        self.assertFalse(
            result["received"],
            "a deaf transport must not be reported as healthy",
        )


if __name__ == "__main__":
    unittest.main()
