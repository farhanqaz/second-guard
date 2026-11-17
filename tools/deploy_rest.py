#!/usr/bin/env python3
"""Deploy the sink and the reactive contract on top of an existing origin contract.

Usage: python3 tools/deploy_rest.py <origin_address>
Prints: origin sink reactive
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import loop  # noqa: E402


def main():
    origin = sys.argv[1]
    topic = loop.sh("cast", "keccak", "Ping(address,uint256,uint256,uint256)").strip()

    sink, sink_tx = loop.create("src/PongSink.sol:PongSink", loop.BASE_RPC, [loop.CALLBACK_PROXY_BASE_SEPOLIA])
    print("sink", sink, sink_tx)

    rc, rc_tx = loop.create(
        "src/PingReactive.sol:PingReactive",
        loop.LASNA_RPC,
        [str(loop.BASE_CHAIN_ID), str(loop.BASE_CHAIN_ID), origin, topic, sink],
    )
    print("reactive", rc, rc_tx)

    fund = loop.send([rc, "--value", "0.02ether"], loop.LASNA_RPC)
    print("fund", fund.get("transactionHash"))


if __name__ == "__main__":
    main()
