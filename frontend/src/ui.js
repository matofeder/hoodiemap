/**
 * initDemoUI wires the search bar.
 * onSearch(lat, lon, displayName) is called when user submits a valid address.
 */
export function initDemoUI(onSearch) {
  const input = document.getElementById('search-input');
  const btn = document.getElementById('search-btn');

  async function handleSearch() {
    const query = input.value.trim();
    if (!query) return;

    btn.disabled = true;
    btn.textContent = '…';

    try {
      const results = await geocode(query);
      if (results.length === 0) {
        alert('Adresa nenájdená. Skús iný text.');
        return;
      }
      const best = results[0];
      const lat = parseFloat(best.lat);
      const lon = parseFloat(best.lon);
      if (isNaN(lat) || isNaN(lon)) throw new Error('Invalid coordinates from geocoder');
      await onSearch(lat, lon, best.display_name);
    } catch (err) {
      alert(`Chyba: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Zobraziť';
    }
  }

  btn.addEventListener('click', handleSearch);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleSearch();
  });
}

async function geocode(query) {
  const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Geocode failed: ${res.status}`);
  return res.json();
}
