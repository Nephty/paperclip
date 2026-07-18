{
  description = "Paperclip Django app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
        lib = pkgs.lib;
        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: [
          ps.django
          ps.gunicorn
          ps.whitenoise
        ]);

        # Source filtered to exclude dev/build cruft from the Nix store.
        src = lib.cleanSourceWith {
          src = ./.;
          filter = path: _type:
            let base = baseNameOf path; in
            !(lib.elem base [
              ".venv" ".git" ".direnv" "staticfiles" "result"
              "__pycache__" "db.sqlite3" "node_modules" ".idea"
            ]);
        };

        # Derivation that collects static files (Django admin CSS/JS) at build time.
        appSrc = pkgs.stdenv.mkDerivation {
          pname = "paperclip-app";
          version = "0.1.0";
          inherit src;
          nativeBuildInputs = [ pythonEnv ];
          dontConfigure = true;

          buildPhase = ''
            runHook preBuild
            export HOME=$TMPDIR
            export DJANGO_SETTINGS_MODULE=config.settings
            export DJANGO_DEBUG=False
            export DJANGO_SECRET_KEY=build-time-only-not-secret
            export PAPERCLIP_STATIC_ROOT=$PWD/staticfiles
            python manage.py collectstatic --noinput
            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p $out/share/paperclip
            cp -r accounts pastes config templates manage.py staticfiles \
                  $out/share/paperclip/
            runHook postInstall
          '';
        };

        appHome = "${appSrc}/share/paperclip";

        # Shell preamble shared by both wrappers. Env vars are overridable so
        # the systemd service (or a manual run) can point to a writable state dir.
        commonEnv = ''
          export DJANGO_SETTINGS_MODULE=config.settings
          export PYTHONPATH=${appHome}''${PYTHONPATH:+:$PYTHONPATH}
          export PAPERCLIP_STATIC_ROOT=''${PAPERCLIP_STATIC_ROOT:-${appHome}/staticfiles}
          export PAPERCLIP_STATE_DIR=''${PAPERCLIP_STATE_DIR:-$PWD/db}
          export PAPERCLIP_DB_PATH=''${PAPERCLIP_DB_PATH:-$PAPERCLIP_STATE_DIR/db.sqlite3}
          export ALLOWED_HOSTS=''${ALLOWED_HOSTS:-*}
        '';

        manageBin = pkgs.writeShellApplication {
          name = "paperclip-manage";
          runtimeInputs = [ pythonEnv ];
          text = ''
            ${commonEnv}
            exec python ${appHome}/manage.py "$@"
          '';
        };

        # Runs migrations then starts gunicorn; WhiteNoise serves static files.
        serverBin = pkgs.writeShellApplication {
          name = "paperclip-server";
          runtimeInputs = [ pythonEnv ];
          text = ''
            ${commonEnv}
            export DJANGO_DEBUG=''${DJANGO_DEBUG:-False}
            BIND=''${PAPERCLIP_BIND:-0.0.0.0:8000}
            WORKERS=''${PAPERCLIP_WORKERS:-3}

            mkdir -p "$PAPERCLIP_STATE_DIR"
            echo "paperclip: migrating (db: $PAPERCLIP_DB_PATH)"
            python ${appHome}/manage.py migrate --noinput
            echo "paperclip: serving on $BIND ($WORKERS workers)"
            exec gunicorn config.wsgi:application \
              --chdir ${appHome} --bind "$BIND" --workers "$WORKERS"
          '';
        };

        paperclip = pkgs.symlinkJoin {
          name = "paperclip-0.1.0";
          paths = [ serverBin manageBin ];
        };
      in
      {
        packages = {
          default = paperclip;
          paperclip = paperclip;
          app = appSrc;
          pythonEnv = pythonEnv;
        };

        # `nix run`           → boots the server (auto-migrates on startup)
        # `nix run .#manage -- createsuperuser` → manage.py passthrough
        apps = {
          default = {
            type = "app";
            program = "${paperclip}/bin/paperclip-server";
          };
          manage = {
            type = "app";
            program = "${paperclip}/bin/paperclip-manage";
          };
        };

        devShells.default = pkgs.mkShell {
          name = "paperclip-shell";
          buildInputs = [
            pkgs.python312
            pkgs.python312Packages.pip
            pkgs.sqlite
            pkgs.git
            pkgs.claude-code
          ];
          shellHook = ''
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi
            source .venv/bin/activate
            pip install -r requirements.txt -q
            mkdir -p db
            echo "Paperclip dev shell — run: python manage.py runserver"
          '';
        };
      }))

    // {
      # NixOS module — add to your server's configuration.nix:
      #   inputs.paperclip.url = "github:you/paperclip";
      #   imports = [ inputs.paperclip.nixosModules.default ];
      #   services.paperclip.enable = true;
      nixosModules.default = { config, pkgs, lib, ... }:
        let cfg = config.services.paperclip;
        in {
          options.services.paperclip = {
            enable = lib.mkEnableOption "Paperclip Django app";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
              description = "The paperclip package to run.";
            };
            bind = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1:8000";
              description = "host:port gunicorn binds to.";
            };
            workers = lib.mkOption {
              type = lib.types.int;
              default = 3;
            };
            allowedHosts = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [ "localhost" "127.0.0.1" ];
              description = "Django ALLOWED_HOSTS (comma-joined into the env var).";
            };
            secretKeyFile = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = "Path to a file containing the Django SECRET_KEY.";
            };
            urlPrefix = lib.mkOption {
              type = lib.types.str;
              default = "";
              description = "URL path prefix this app is reverse-proxied under (e.g. \"/paperclip\"). Empty means served at the domain root.";
            };
            signupPasswordHashFile = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = ''
                Path to a file containing the hashed admin password checked on the
                hidden signup form (produced via Django's make_password, not
                plaintext). Generate it out-of-band and never commit it:
                  python manage.py shell -c "from django.contrib.auth.hashers import make_password; print(make_password('the-actual-secret'))"
              '';
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.services.paperclip = {
              description = "Paperclip";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];
              environment = {
                DJANGO_DEBUG = "False";
                ALLOWED_HOSTS = lib.concatStringsSep "," cfg.allowedHosts;
                PAPERCLIP_BIND = cfg.bind;
                PAPERCLIP_WORKERS = toString cfg.workers;
                PAPERCLIP_STATE_DIR = "/var/lib/paperclip";
                PAPERCLIP_DB_PATH = "/var/lib/paperclip/db.sqlite3";
                DJANGO_FORCE_SCRIPT_NAME = cfg.urlPrefix;
              };
              serviceConfig = {
                ExecStart = pkgs.writeShellScript "paperclip-start" ''
                  ${lib.optionalString (cfg.secretKeyFile != null) ''
                    DJANGO_SECRET_KEY="$(cat ${cfg.secretKeyFile})"
                    export DJANGO_SECRET_KEY
                  ''}
                  ${lib.optionalString (cfg.signupPasswordHashFile != null) ''
                    SIGNUP_GATE_PASSWORD_HASH="$(cat ${cfg.signupPasswordHashFile})"
                    export SIGNUP_GATE_PASSWORD_HASH
                  ''}
                  exec ${cfg.package}/bin/paperclip-server
                '';
                DynamicUser = true;
                StateDirectory = "paperclip";
                Restart = "on-failure";
                RestartSec = 2;
              };
            };
          };
        };
    };
}
