module.exports = {
  apps: [
    {
      name: 'geo-backend',
      script: 'python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8765',
      cwd: __dirname,
      env: {
        ENVIRONMENT: 'development',
      },
      env_production: {
        ENVIRONMENT: 'production',
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      merge_logs: true,
      time: true,
    },
    {
      name: 'geo-worker',
      script: 'python',
      args: '-m arq app.services.pipeline.arq_worker.WorkerSettings',
      cwd: __dirname,
      env: {
        ENVIRONMENT: 'development',
        REDIS_URL: 'redis://localhost:6379',
      },
      env_production: {
        ENVIRONMENT: 'production',
        REDIS_URL: 'redis://localhost:6379',
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: './logs/worker-error.log',
      out_file: './logs/worker-out.log',
      merge_logs: true,
      time: true,
    },
  ],
};
