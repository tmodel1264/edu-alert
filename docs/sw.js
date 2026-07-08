// 홈 화면 앱 설치용 최소 서비스워커 (푸시 알림은 2단계에서 추가 예정)
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
self.addEventListener('fetch', () => {});
