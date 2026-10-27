# Apple trust anchors

Public Apple Root CA G2 and G3 DER certificates from
https://www.apple.com/certificateauthority/ (retrieved October 27, 2026).
These are public verification roots, not private keys.

| File | SHA-256 |
| --- | --- |
| AppleRootCA-G2.cer | c2b9b042dd57830e7d117dac55ac8ae19407d38e41d88f3215bc3a890444a050 |
| AppleRootCA-G3.cer | 63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179 |

Source files: `https://www.apple.com/certificateauthority/AppleRootCA-G2.cer`
and `https://www.apple.com/certificateauthority/AppleRootCA-G3.cer`.
The official App Store Server Library verifies the certificate chain, online
revocation status, bundle, environment, app ID and signed payloads. Update these
roots only from Apple's official certificate authority page and review hashes.
