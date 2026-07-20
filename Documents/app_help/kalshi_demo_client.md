# Kalshi DEMO client (r1632)

**Mock money only. Production USD OFF.**

## Status

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 System/kalshi_demo_client.py --status
python3 System/kalshi_demo_client.py --self-test
```

## Install demo keys (George only, Keychain)

```bash
security add-generic-password -s sifta.kalshi.demo -a api_key_id -w 'YOUR_DEMO_KEY_ID'
security add-generic-password -s sifta.kalshi.demo -a private_key_pem -w "$(cat path/to/demo.pem)"
```

Never commit pem files. Prod hosts raise inside the client.

## Kill switch

```bash
python3 System/kalshi_demo_client.py --kill    # arm
python3 System/kalshi_demo_client.py --unkill  # clear
```

## Pilot (shadow / report)

```bash
python3 System/kalshi_demo_pilot.py --once
python3 System/kalshi_demo_pilot.py --report
```

R4 ($10 real) is **not** in this code path.
