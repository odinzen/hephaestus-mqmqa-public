# Security

Hephaestus is built to run on machines that cannot send data anywhere, including air-gapped
networks.

## What leaves the machine

Nothing. The browser app (`web/`) is static files. Both pages carry a Content-Security-Policy
that allows connections only to the server the page came from (`connect-src 'self'`), so a
third-party request is refused by the browser itself. Fonts and Three.js are bundled in `web/`,
and the engine is compiled into `web/hephaestus.js`. A database you load is read inside the
page and never uploaded. The browser keeps two things locally: display preferences in
`localStorage`, and finished 3D surfaces in IndexedDB so a restart does not recompute them.
Clearing site data removes both.

The C library and the Python package make no network calls.

## Running offline

Copy `web/` to the target machine and serve it from any static web server, for example

    cd web && python -m http.server 8123

then open http://localhost:8123. No install step, package download, or build is needed.

## Verifying a release

Each release is archived on Zenodo with a DOI, and Zenodo lists a checksum for every archived
file. Compare it against the archive you downloaded before deploying.

## Reporting a vulnerability

Email michaelbusta@odinzen.io with a description and, if possible, a file or steps that
reproduce it. Please do not open a public issue for a security problem.
