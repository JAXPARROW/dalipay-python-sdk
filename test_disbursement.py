#!/usr/bin/env python
"""
Test script for Dalipay SDK disbursements functionality.

Reads credentials from .env (see .env.example) - do not hardcode keys here.

⚠️  If DALIPAY_PUBLIC_KEY/DALIPAY_SECRET_KEY in your .env are
    gw_pk_production_.../gw_sk_production_..., running this sends REAL
    money to a REAL phone number. This script will refuse to run against
    production keys unless you explicitly pass --live-production.

Run with: python test_disbursement.py
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


def test_create_disbursement():
    """Test creating a disbursement and polling its status."""

    client = Dalipay(PUBLIC_KEY, SECRET_KEY, BASE_URL)

    try:
        print("=" * 50)
        print("Testing Create Disbursement")
        print("=" * 50)

        amount = 1000
        external_id = f"PAYOUT-{int(time.time())}"
        print(f"\n1. Creating disbursement of {amount} TZS...")

        # provider is omitted here - the SDK guesses it from
        # TEST_PHONE_NUMBER's prefix. Pass provider explicitly if you
        # already know the recipient's actual network.
        disbursement = client.create_disbursement(
            account_number=TEST_PHONE_NUMBER,
            amount=amount,
            external_id=external_id,
            recipient_name="Juma Hassan",
            remarks="Test payout from SDK",
        )

        print(f"\n✅ Disbursement created successfully!")
        print(f"   UUID: {disbursement.uuid}")
        print(f"   Reference: {disbursement.reference}")
        print(f"   Status: {disbursement.status}")
        print(f"   Amount: {disbursement.amount}")

        print("\n2. Polling disbursement status...")
        time.sleep(2)

        status = client.get_disbursement_status(disbursement.reference)
        print(f"   Status: {status.status}")

        return disbursement

    except DalipayError as e:
        print(f"\n❌ Error: {e.message}")
        print(f"   HTTP Code: {e.code}")
        return None
    finally:
        client.close()


if __name__ == "__main__":
    print("🔧 DALIPAY SDK DISBURSEMENT TEST")
    print("=" * 50)

    if not (PUBLIC_KEY and SECRET_KEY and BASE_URL):
        print("Missing DALIPAY_PUBLIC_KEY / DALIPAY_SECRET_KEY / DALIPAY_BASE_URL.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    is_production = "_production_" in PUBLIC_KEY or "_production_" in SECRET_KEY

    if is_production and "--live-production" not in sys.argv:
        print("⚠️  DALIPAY_PUBLIC_KEY/SECRET_KEY in .env are PRODUCTION keys.")
        print("   Running this script will send REAL money to")
        print(f"   {TEST_PHONE_NUMBER}.")
        print()
        print("   Re-run with --live-production to proceed anyway, after")
        print("   double-checking TEST_PHONE_NUMBER and the amount above.")
        sys.exit(1)

    print(f"Using base URL: {BASE_URL}")
    print(f"Mode: {'PRODUCTION (live)' if is_production else 'test'}")
    print()

    test_create_disbursement()

    print("\n" + "=" * 50)
    print("Tests completed!")
