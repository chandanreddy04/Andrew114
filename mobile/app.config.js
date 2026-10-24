// Adds build-time settings on top of app.json.
//
// Development and preview (test) builds may talk to an API over plain
// http:// (e.g. the dev server on your laptop over Wi-Fi). Production builds
// can't: Android then only allows HTTPS. See eas.json (ALLOW_HTTP_API).
module.exports = ({ config }) => ({
  ...config,
  plugins: [
    ...(config.plugins ?? []),
    [
      'expo-build-properties',
      { android: { usesCleartextTraffic: process.env.ALLOW_HTTP_API === '1' } },
    ],
  ],
});
