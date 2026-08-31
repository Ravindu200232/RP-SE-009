"""The Fooocus address comes from Settings alone.

There used to be a built-in ``DEFAULT_HOSTS`` fallback to 127.0.0.1:7865/:7860, so a
machine that had never configured Fooocus still probed one, and a mistyped remote
address was masked by whatever happened to be listening locally. These tests pin the
replacement: an unset address is reported, never guessed.
"""
import unittest
from unittest.mock import patch

from agents.features import image_generator
from agents.features.image_generator import ImageAgent
from agents.features.image_settings import NO_HOST_SET, is_local_host


class ImageHostResolutionTests(unittest.TestCase):
    def test_an_unset_address_is_never_probed(self):
        """With nothing configured there is no address to try, so nothing is tried."""
        agent = ImageAgent(host="", enabled=True)
        with patch.object(image_generator.requests, "get") as get:
            self.assertEqual(agent.base_url(), "")
        get.assert_not_called()
        self.assertEqual(agent.probe()["reason"], NO_HOST_SET)

    def test_no_local_default_is_reintroduced(self):
        """A configured address is the only one contacted."""
        agent = ImageAgent(host="https://gpu.example.com", enabled=True)
        with patch.object(image_generator.requests, "get",
                          side_effect=image_generator.requests.RequestException("nope")) as get:
            self.assertEqual(agent.base_url(), "")
        tried = [call.args[0] for call in get.call_args_list]
        self.assertEqual(tried, ["https://gpu.example.com/config"])

    def test_the_three_unavailable_states_stay_distinguishable(self):
        """Off, unset, and unreachable must not collapse into one message."""
        off = ImageAgent(host="http://127.0.0.1:7865", enabled=False).why_unavailable()
        unset = ImageAgent(host="", enabled=True).why_unavailable()
        with patch.object(image_generator.requests, "get",
                          side_effect=image_generator.requests.RequestException("nope")):
            unreachable = ImageAgent(host="http://127.0.0.1:7865",
                                     enabled=True).why_unavailable()
        self.assertIn("switched off", off)
        self.assertEqual(unset, NO_HOST_SET)
        self.assertIn("127.0.0.1:7865", unreachable)
        self.assertEqual(len({off, unset, unreachable}), 3)


class LocalHostDetectionTests(unittest.TestCase):
    """Only an address on this machine may trigger the local Fooocus launcher."""

    def test_addresses_on_this_machine(self):
        for host in ("127.0.0.1:7865", "http://localhost:7860", "http://LOCALHOST:7865",
                     "http://[::1]:7865", "0.0.0.0:7865"):
            with self.subTest(host=host):
                self.assertTrue(is_local_host(host))

    def test_addresses_somewhere_else(self):
        for host in ("", "https://gpu.example.com", "my-gpu-box.lan:7865",
                     "https://quiet-frog-42.trycloudflare.com", "http://192.168.1.9:7865"):
            with self.subTest(host=host):
                self.assertFalse(is_local_host(host))


if __name__ == "__main__":
    unittest.main()
