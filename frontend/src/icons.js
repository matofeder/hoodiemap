const PATHS = {
  hospital: '<path d="M12 5v14M5 12h14"/>',
  supermarket: '<path d="M3 4h2l2.4 10.5h10.2L20 8H6.3"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>',
  school: '<path d="M2 9.5 12 5l10 4.5L12 14z"/><path d="M6 11.5V16c3.5 2.5 8.5 2.5 12 0v-4.5"/>',
  kindergarten: '<rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/><rect x="8.5" y="4" width="7" height="7" rx="1"/>',
  pharmacy: '<rect x="3" y="8.5" width="18" height="7" rx="3.5" transform="rotate(-45 12 12)"/><path d="M9.5 9.5l5 5"/>',
  bus_stop: '<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 10h14M8 20v-3M16 20v-3"/>',
  train: '<rect x="6" y="3" width="12" height="13" rx="3"/><path d="M6 10h12M9 20l1.5-3M15 20l-1.5-3"/>',
  park: '<path d="M12 3 18 12H6z"/><path d="M12 12v8"/>',
  pin: '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10z"/><circle cx="12" cy="11" r="2"/>',
  arrow: '<path d="M4 12h15M13 6l6 6-6 6"/>',
  north: '<path d="M12 3l5 14-5-3-5 3z"/>',
};

export function iconSvg(name) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${PATHS[name] ?? '<circle cx="12" cy="12" r="4"/>'}</svg>`;
}
