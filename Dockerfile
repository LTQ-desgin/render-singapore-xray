FROM ghcr.io/xtls/xray-core:26.10.31@sha256:ceabeac03a89d991d2a247361825c1d1d2e9c91cd5dc010f298c7dc0c2f325c9 AS xray
FROM alpine:3.22
RUN apk add --no-cache ca-certificates nginx python3 && addgroup -S -g 10001 app && adduser -S -D -H -u 10001 -G app app
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY app.py /app/app.py
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python3", "/app/app.py"]
