module.exports = {
  apps: [
    {
      name: 'geo-backend',
      script: 'python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8000',
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
  ],
};
