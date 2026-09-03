"""Provider-agnostic integration channels for the Co-Pilot.

Each channel (WhatsApp, …) is a small package under ``channels/`` exposing a
provider ABC + concrete implementations + a registry — mirroring the
freight-exchange adapter precedent (§17).  The Co-Pilot never understands a
channel individually; it only orchestrates the deterministic provider methods.
"""