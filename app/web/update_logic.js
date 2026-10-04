'use strict';
// Shared by the browser and the regression checks.
const UpdateLogic = {
  settingsCenter(previous, next) {
    const unchanged = next.map_latitude === previous.map_latitude && next.map_longitude === previous.map_longitude;
    const followedStation = previous.map_latitude === previous.latitude && previous.map_longitude === previous.longitude;
    const unset = previous.map_latitude === 0 && previous.map_longitude === 0;
    return unchanged && (followedStation || unset)
      ? [next.latitude, next.longitude] : [next.map_latitude, next.map_longitude];
  },
  initialCenter(config, manifest) {
    if (config.map_latitude !== 0 || config.map_longitude !== 0) return [config.map_latitude, config.map_longitude];
    if (config.latitude !== 0 || config.longitude !== 0) return [config.latitude, config.longitude];
    if (manifest?.center) return manifest.center;
    const r = manifest?.region;
    return r ? [(r[1] + r[3]) / 2, (r[0] + r[2]) / 2] : [0, 0];
  },
  errorText(serverError, clientError) { return clientError || serverError || ''; }
};
if (typeof module !== 'undefined') module.exports = UpdateLogic;
