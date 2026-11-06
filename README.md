# Singapore deployment

Builds a shell-capable Alpine image by copying Xray from the official pinned image.
Xray listens internally on 3000; nginx accepts Render traffic on PORT (8080).
Render terminates public TLS on 443.

Set VLESS_UUID to a UUID and WS_TOKEN and SUB_TOKEN to independent random hex strings
of 32-64 characters in Render's environment settings. Credentials are never committed.
RENDER_EXTERNAL_HOSTNAME is provided by Render.

The private subscription is served at https://YOUR_HOST/SUB_TOKEN/clash.yaml.
The JSON document is valid YAML and contains a full Mihomo/Clash Verge configuration.
Only people possessing that link should receive it: it includes the node credential.

Select Singapore and the Free compute plan. No persistent storage or paid add-ons.
Render Free services sleep after inactivity and remain subject to platform usage limits.
