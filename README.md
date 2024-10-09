# Pierdat

Docker containers and VMs that serve their own data. Peer to peer, or pier to
pier I guess.

Status: work in progress.

## todo

* write some tests
* write some more backends 

## Usage

* Add the `./root` dir to your Dockerfile at /
* Install one of the supported p2p backends via your preferred method.
* Add one or more `RUN pierdat src dest` lines to your Dockerfile.
* If you're building a VM (or you've got a weird Docker image with an init
  daemon), run `update-rc.d pierdatd defaults`, otherwise use the
  `/entrypoint.sh` provided like in the example.
* Build it, it'll get the data from seeds as it builds.
* Run it, it'll seed the data to other people who are building it.

See [Dockerfile-ubuntu](./Dockerfile-ubuntu) for an example.

If you used `RUN --network=host pierdat` like in the example, you'll need to
build it with `--allow=network.host` set.

```sh
docker buildx build --allow=network.host -t mashup -f Dockerfile-ubuntu .
```

## How it works

`pierdat` is a shell script that lives in `/usr/bin`, it checks for the presence
of `/usr/bin/pierdat-{check,get}-{backend}` scripts. For each backend it first
runs the check against the given URI, then it runs the get script to download
the data.

If the get script is successful, its output is added to the runtime config file
in `/etc/pier.dat`; the output is the command needed to run the seed script.

At runtime, it will `pierdatd`. This will spawn a process for each line in the
config file, acting as a watchdog and restarting them as required.

## Hacking

Licensed under the WTFPL with a warranty clause - do whatever you want, as long
as you don't blame me. Pull requests welcome.

To add a backend, just create at least the first two of these scripts in
`./root/usr/bin/`:

* `pierdat-check-backend-name <URI>` -
  check to see if the backend is available; i.e. the program exists available
  and the URI is valid. exit with a nonzero status code to indicate failure.
  output warnings and errors to stderr if you want them to be seen in Docker's
  log at build time.
* `pierdat-get-backend-name <URI> <PATH>` - download the data and exit. If
  successful then print the lines needed to seed this file at runtime, and exit
  with status 0. Otherwise exist with something else.
* `pierdat-seed-backend-name ...` - called to seed your data using the output
  of the above. Optional, since you can use whatever command you like to seed,
  but the program should stay running while the download is happening.

The scripts provided are plain old shell scripts, so it supports lightweight
base images that don't come with bash (e.g. alpine). You can use whatever you
want, as long as the interpreter is a dependency of the backend you're adding.
