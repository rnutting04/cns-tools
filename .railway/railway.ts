import { bucket, defineRailway, github, postgres, project, redis, service, volume } from "railway/iac";

export default defineRailway(() => {
  const cnsTools = github("rnutting04/cns-tools", { branch: "main", checkSuites: true, rootDirectory: "/backend" });

  const Postgres = postgres("Postgres", { region: "sfo" });
  Postgres.deploy = { multiRegionConfig: { sfo: { numReplicas: 1 } } };
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const Redis = redis("Redis", { region: "sfo" });
  Redis.deploy = { multiRegionConfig: { sfo: { numReplicas: 1 } }, startCommand: "/bin/sh -c \"rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH\"" };
  Redis.networking = { privateNetworkEndpoint: "redis" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "sfo", sizeMB: 500 });
  const redisVolume = volume("redis-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "sfo", sizeMB: 500 });
  const indexedBarrow = bucket("indexed-barrow", { region: "iad" });
  const imaginativePeace = service("imaginative-peace", {
    source: cnsTools,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    start: "sh -c 'gunicorn app.main:app --bind 0.0.0.0:$PORT --workers 2 --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - --timeout 60'",
    healthcheck: "/health",
    healthcheckTimeout: 30,
    preDeploy: "alembic upgrade head",
    replicas: { "us-east4-eqdc4a": 1 },
  });
  // The backend services share one image. Its default command starts the API,
  // so every worker MUST set its own start command. (Was railway.light.toml /
  // railway.worker.toml, which `config migrate` didn't pick up.)
  const backendBuild = { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" } as const;

  // Light worker: letters, emails, nightly cleanup ("light" queue).
  const generousCuriosity = service("generous-curiosity", {
    source: cnsTools,
    build: backendBuild,
    start: "celery -A app.celery_app.celery_app worker -Q light --concurrency=2 --loglevel=info",
    replicas: { "sfo": 1 },
  });
  // Long-jobs worker: budgets, accounting runs ("default" queue).
  const incredibleCompassion = service("incredible-compassion", {
    source: cnsTools,
    build: backendBuild,
    start: "celery -A app.celery_app.celery_app worker -Q default --concurrency=4 --loglevel=info",
    replicas: { "sfo": 1 },
  });
  // Scheduler (Celery beat): puts nightly cleanup (and later reminder emails)
  // on the queue; the workers run them. Exactly ONE replica, or every
  // scheduled task runs once per copy. Variables are unmanaged: copy the light
  // worker's into this service in the dashboard (Variables → Raw Editor).
  const scheduler = service("scheduler", {
    source: cnsTools,
    build: backendBuild,
    start: "celery -A app.celery_app.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule",
    replicas: { "sfo": 1 },
  });
  const cnsTools2 = service("cns-tools", {
    source: github("rnutting04/cns-tools", { branch: "main", checkSuites: true, rootDirectory: "/frontend" }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    replicas: { "sfo": 1 },
    domains: [{ domain: "tools.cscmsi.net", port: 80 }],
  });

  return project("artistic-strength", {
    variables: { managed: false },
    resources: [imaginativePeace, Postgres, generousCuriosity, incredibleCompassion, scheduler, Redis, cnsTools2, postgresVolume, redisVolume, indexedBarrow],
  });
});
