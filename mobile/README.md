# Androyit: Android app

Expo SDK 57 / React Native app. It talks only to the Reached API in
[`../backend`](../backend) (see [`../docs/API.md`](../docs/API.md)).

```bash
npm install
cp .env.example .env.local   # EXPO_PUBLIC_API_URL = where the API runs
npx expo start               # open in Expo Go, or press "a" for the emulator
```

Checks: `npx tsc --noEmit` and `npx expo lint`.
Builds: see [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md#4-the-android-app).
