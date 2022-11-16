import pulumi
import pulumi_digitalocean as digitalocean

# Our stack-specific configuration.
config = pulumi.Config()
repo = config.require("repo")
branch = config.require("branch")

# The DigitalOcean region to deploy into.
region = digitalocean.Region.SFO3

# ...

# Our MongoDB cluster (currently just one node).
cluster = digitalocean.DatabaseCluster("cluster", digitalocean.DatabaseClusterArgs(
    engine = "mongodb",
    version = "5",
    region = region,
    size = digitalocean.DatabaseSlug.D_B_1_VPCU1_GB,
    node_count = 1
))

# The database we'll use for our grocery list.
db = digitalocean.DatabaseDb("db", digitalocean.DatabaseDbArgs(
    name = "grocery-list",
    cluster_id = cluster.id
))

# ...

# The App Platform spec that defines our grocery list.
app = digitalocean.App("app", digitalocean.AppArgs(
    spec = digitalocean.AppSpecArgs(
        name = "grocery-list",
        region = region,

        # The React front end.
        static_sites = [
            digitalocean.AppSpecStaticSiteArgs(
                name = "frontend",
                github = digitalocean.AppSpecJobGithubArgs(
                    repo = repo,
                    branch = branch,
                    deploy_on_push = True
                ),
                source_dir = "/frontend",
                build_command = "npm install && npm run build",
                output_dir = "/dist"
            )
        ],

        # The Express back end.
        services = [
            digitalocean.AppSpecServiceArgs(
                name = "backend",
                github = digitalocean.AppSpecJobGithubArgs(
                    repo = repo,
                    branch = branch,
                    deploy_on_push = True
                ),
                source_dir = "/backend",
                build_command = "npm install && npm run build",
                run_command = "npm start",
                http_port = 8000,
                routes = [
                    digitalocean.AppSpecServiceRouteArgs(
                        path = "/api",
                        preserve_path_prefix = True
                    )
                ],
                instance_size_slug = "basic-xxs",
                instance_count = 1,

                # To connect to MongoDB, the service needs a DATABASE_URL, which
                # is conveniently exposed as an environment variable because the
                # database belongs to the app (see below).
                envs = [
                    digitalocean.AppSpecServiceEnvArgs(
                        key = "DATABASE_URL",
                        scope = "RUN_AND_BUILD_TIME",
                        value = "${db.DATABASE_URL}"
                    )
                ]
            )
        ],

        # Include the MongoDB cluster as an integrated App Platform component.
        databases = [
            digitalocean.AppSpecDatabaseArgs(
                # The `db` name defines the prefix of the tokens used (above) to
                # read the environment variables exposed by the database cluster.
                name = "db",

                # MongoDB clusters are only available in "production" mode.
                # https://docs.digitalocean.com/products/app-platform/concepts/database/
                production = True,

                # A reference to the managed cluster we declared above.
                cluster_name = cluster.name,

                # The engine value must be uppercase, so we transform it with Python.
                engine = cluster.engine.apply(lambda engine: engine.upper())
            )
        ]
    ),
))

# ...

# Adding a database firewall setting restricts access solely to our app.
trusted_source = digitalocean.DatabaseFirewall("trusted-source", digitalocean.DatabaseFirewallArgs(
    cluster_id = cluster.id,
    rules = [
        digitalocean.DatabaseFirewallRuleArgs(
            type = "app",
            value = app.id
        )
    ],
))

# ...

# The DigitalOcean-assigned URL for our app.
pulumi.export("liveUrl", app.live_url)
