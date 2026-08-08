#!/usr/bin/env python
"""
Test script for Dalipay SDK collections functionality.

Reads credentials from .env (see .env.example) - do not hardcode keys here.

⚠️  If DALIPAY_PUBLIC_KEY/DALIPAY_SECRET_KEY in your .env are
    gw_pk_production_.../gw_sk_production_..., running this sends a REAL
    USSD prompt to a REAL phone number and moves REAL money. This script
    will refuse to run against production keys unless you explicitly pass
    --live-production.

Run with: python test_collection.py
"""

import os
import sys
import time

from dotenv import load_dotenv

from dalipay import Dalipay
from dalipay.exceptions import DalipayError

load_dotenv()

PUBLIC_KEY = os.environ.get("DALIPAY_PUBLIC_KEY", "")
SECRET_KEY = os.environ.get("DALIPAY_SECRET_KEY", "")
BASE_URL = os.environ.get("DALIPAY_BASE_URL", "")

# Update this to a real phone number you control before running.
TEST_PHONE_NUMBER = "0712345678"


def test_create_collection():
    """Test creating a collection and polling its status."""

    client = Dalipay(PUBLIC_KEY, SECRET_KEY, BASE_URL)

    try:
        print("=" * 50)
        print("Testing Create Collection")
        print("=" * 50)

        amount = 1000
        external_id = f"INV-{int(time.time())}"
        print(f"\n1. Creating collection of {amount} TZS...")
        # provider is omitted here - the SDK guesses it from
        # TEST_PHONE_NUMBER's prefix. Pass provider explicitly if you
        # already know the customer's actual network.
        collection = client.create_collection(
            account_number=TEST_PHONE_NUMBER,
            amount=amount,
            external_id=external_id,
            customer_name="Asha Mwakasege",
        )

        print(f"\n✅ Collection created successfully!")
        print(f"   UUID: {collection.uuid}")
        print(f"   Reference: {collection.reference}")
        print(f"   Status: {collection.status}")
        print(f"   Amount: {collection.amount} {collection.currency}")

        print("\n2. Waiting for the customer to respond (up to 5 minutes)...")
        result = client.wait_for_collection(collection.uuid, timeout=300, interval=3)
        print(f"   Status: {result.status}")

        return result

    except DalipayError as e:
        print(f"\n❌ Error: {e.message}")
        print(f"   HTTP Code: {e.code}")
        return None
    finally:
        client.close()


if __name__ == "__main__":
    print("🔧 DALIPAY SDK COLLECTION TEST")
    print("=" * 50)

    if not (PUBLIC_KEY and SECRET_KEY and BASE_URL):
        print("Missing DALIPAY_PUBLIC_KEY / DALIPAY_SECRET_KEY / DALIPAY_BASE_URL.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    is_production = "_production_" in PUBLIC_KEY or "_production_" in SECRET_KEY

    if is_production and "--live-production" not in sys.argv:
        print("⚠️  DALIPAY_PUBLIC_KEY/SECRET_KEY in .env are PRODUCTION keys.")
        print("   Running this script will send a REAL USSD prompt to")
        print(f"   {TEST_PHONE_NUMBER} and move REAL money.")
        print()
        print("   Re-run with --live-production to proceed anyway, after")
        print("   double-checking TEST_PHONE_NUMBER and the amount above.")
        sys.exit(1)

    print(f"Using base URL: {BASE_URL}")
    print(f"Mode: {'PRODUCTION (live)' if is_production else 'test'}")
    print()

    test_create_collection()

    print("\n" + "=" * 50)
    print("Tests completed!")
