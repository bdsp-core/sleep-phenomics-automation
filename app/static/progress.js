(function (root) {
    function formatDuration(totalSeconds) {
        const seconds = Math.max(0, Math.round(Number(totalSeconds) || 0));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;

        if (hours > 0) return `${hours}h ${minutes}m ${remainder}s`;
        if (minutes > 0) return `${minutes}m ${remainder}s`;
        return `${remainder}s`;
    }

    function parseDuration(value) {
        const match = String(value || '').trim().match(/^([\d.]+)\s*(second|minute|hour)s?$/i);
        if (!match) return 0;

        const multipliers = {second: 1, minute: 60, hour: 3600};
        return Number(match[1]) * multipliers[match[2].toLowerCase()];
    }

    function uploadSnapshot(loaded, total, elapsedSeconds) {
        const safeTotal = Number(total);
        const safeLoaded = Math.max(0, Number(loaded) || 0);
        const elapsed = Math.max(0, Number(elapsedSeconds) || 0);
        const percent = safeTotal > 0
            ? Math.min(100, Math.round((safeLoaded / safeTotal) * 100))
            : 0;
        const bytesPerSecond = elapsed > 0 ? safeLoaded / elapsed : 0;
        const remainingSeconds = safeTotal > safeLoaded && bytesPerSecond > 0
            ? Math.ceil((safeTotal - safeLoaded) / bytesPerSecond)
            : 0;

        return {percent, remainingSeconds};
    }

    function computationSnapshot(elapsedSeconds, estimatedSeconds) {
        const elapsed = Math.max(0, Number(elapsedSeconds) || 0);
        const estimate = Math.max(0, Number(estimatedSeconds) || 0);

        if (estimate === 0) {
            return {percent: 0, remainingSeconds: null};
        }

        return {
            percent: Math.min(95, Math.round((elapsed / estimate) * 100)),
            remainingSeconds: Math.max(0, Math.ceil(estimate - elapsed)),
        };
    }

    function selectedFeatureEstimate(selectedFeatures, runningTimes) {
        const selected = new Set(selectedFeatures || []);
        if (selected.has('from_annotation')) {
            selected.delete('sleep_staging_CAISR');
        } else {
            selected.delete('from_annotation');
            selected.add('sleep_staging_CAISR');
        }

        let total = 0;
        selected.forEach(feature => {
            total += parseDuration((runningTimes || {})[feature]);
        });
        return total;
    }

    root.SPAProgress = {
        formatDuration,
        parseDuration,
        uploadSnapshot,
        computationSnapshot,
        selectedFeatureEstimate,
    };
})(typeof window !== 'undefined' ? window : globalThis);
