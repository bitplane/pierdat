# 🐳 Pierdat

Docker containers and VMs that serve their own data. Peer to peer, or pier to
pier I guess.

Status: proof of concept, not battle tested and likely very insecure.

## ✅ todo

* ❌ cross network seeding
* ❌ end-to-end IPFS validation
* ❌ hypercore
* ❌ e2dk
* ❌ web

## ▶️  Usage

1. Add the `./root` dir to your Dockerfile at /
2. Install one of the supported p2p backends and `setsid` (provided by
   util-linux or BusyBox) via your preferred method.
3. Add one or more `RUN pierdat src dest` lines to your Dockerfile.
4. If you're building a VM (or you've got a weird Docker image with an init
   daemon), run `update-rc.d pierdatd defaults`, otherwise use the
   `/entrypoint.sh` provided like in the example.
5. Build it, it'll get the data from seeds as it builds.
6. Run it, it'll seed the data to other people who are building it.

See the [BitTorrent magnet example](examples/aria2/Dockerfile-magnet), which
downloads and seeds using aria2c. It needs peers serving the requested content.

When `RUN --network=host pierdat` is used, the image needs to be built with the
`--allow=network.host` option set. Example:

```sh
docker buildx build --load --allow=network.host -t mashup -f ./examples/aria2/Dockerfile-magnet .
docker run --rm --network=host mashup
```

The example uses host networking on Linux so peers can reach the seeder's
listening ports. The builder must permit the `network.host` entitlement.

The experimental IPFS backend requires Kubo, an initialized local repository,
and its daemon running during the build. Set `IPFS_PATH` to the repository you
will retain in the image. Downloads are resolved and pinned there; runtime
seeding starts one daemon per repository. Preserve the repository as well as the
exported files. There is currently no validated IPFS Docker example. See the
[Kubo CLI reference](https://docs.ipfs.tech/reference/kubo/cli/) for setup.

## ❓ How it works

`pierdat` is a shell script that lives in `/usr/bin`, it checks for the presence
of `/usr/bin/pierdat-{check,get}-{backend}` scripts. For each backend it first
runs the check against the given URI, then it runs the get script to download
the data.

If the get script is successful, its output is added to the runtime config file
in `/etc/pier.dat`; the output is the command needed to run the seed script.

At runtime, `pierdatd` supervises each distinct command in the config file and
restarts exited seeders after a two-second delay. On shutdown it signals each
seeder's process group, allows five seconds for cleanup, and kills any remaining
processes. Seeder output goes to `/var/log/pierdat.log`.

Configuration lines are trusted shell commands. Backends use `pierdat-command`
to quote arguments safely; embedded line breaks are rejected. Rebuild older
images to regenerate commands in this format, and quote any manually maintained
commands. Magnet downloads retain torrent metadata alongside their payloads so
runtime seeding can load it without retrieving metadata from peers again.

## 🧑‍💻 Hacking

Licensed under the WTFPL with a warranty clause - do whatever you want, as long
as you don't blame me. Pull requests welcome.

To add a backend, just create at least the first two of these scripts in
`./root/usr/bin/`:

1. `pierdat-check-backend-name <URI>` -
   check to see if the backend is available; i.e. the program exists available
   and the URI is valid. exit with a nonzero status code to indicate failure.
   output warnings and errors to stderr if you want them to be seen in Docker's
   log at build time.
2. `pierdat-get-backend-name <URI> <PATH>` - download the data and exit. If
   successful then print the lines needed to seed this file at runtime, and exit
   with status 0. Use `pierdat-command executable arg...` to serialize each
   command, and send diagnostics to stderr. Otherwise exit with a nonzero status;
   output from failed backends is discarded.
3. `pierdat-seed-backend-name ...` - called to seed your data using the output
   of the above. Optional, since you can use whatever command you like to seed,
   but the program should stay running while the download is happening.

The scripts provided are plain old shell scripts, so it supports lightweight
base images that don't come with bash (e.g. alpine). You can use whatever you
want, as long as the interpreter is a dependency of the backend you're adding.
Backend scripts must be executable; their shebang determines the interpreter.

Run the regression checks with Python 3 and ShellCheck installed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
shellcheck root/entrypoint.sh root/etc/init.d/pierdatd root/usr/bin/*
```

The regression suite uses isolated temporary files and mock download clients;
it does not download public torrents or validate live IPFS transfers.

## 🔗 Links

* [🏠 home](https://bitplane.net/dev/sh/pierdat)
* [🐱 github](https://github.com/bitplane/pierdat)

