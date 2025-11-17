# Gonka C Tracker


## Backend (port 8081)

cd /backend2


pm2 start npm --name 'back' -- run start


(npm run start)

## Frontend (port 4173)

cd /frontend

npm run build

pm2 start npm --name 'front' -- run preview

(npm run preview)


