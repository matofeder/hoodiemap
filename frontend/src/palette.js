export const PALETTE = {
  slabTop: '#CFE8B9',
  slabSide: '#B4D39C',
  park: '#B9E0A0',
  forest: '#9CCB86',
  water: '#8FD3F4',
  road: '#FBF6EC',
  path: '#F3EBDA',
  roadDash: '#F6C85F',
  walls: ['#FFF4E6', '#FDE2E4', '#E3F1EC', '#E2E8FD', '#FFF6CC'],
  roofs: ['#F28482', '#F6BD60', '#84A59D', '#8E9AAF', '#E07A5F'],
  otherWalls: '#E9E4DA',
  propertyWalls: '#FFFFFF',
  property: '#FF5A5F',
  trunk: '#A1785C',
  crowns: ['#86C98A', '#A1D9B4', '#6DB57A'],
  cars: ['#FF7B7B', '#5CA8FF', '#FFC94D', '#9C7CF4'],
  carCabin: '#EAF4FF',
};

export const CATEGORIES = {
  hospital: { label: 'Nemocnica', color: '#E05252' },
  supermarket: { label: 'Supermarket', color: '#3E9E6B' },
  school: { label: 'Škola', color: '#4A90D9' },
  kindergarten: { label: 'Škôlka', color: '#F2A541' },
  pharmacy: { label: 'Lekáreň', color: '#3AAFA9' },
  bus_stop: { label: 'Zastávka', color: '#7B5EA7' },
  train: { label: 'Stanica', color: '#7F8C8D' },
  park: { label: 'Park', color: '#5FAF6E' },
};

export function categoryInfo(category) {
  return CATEGORIES[category] ?? { label: category, color: '#7F8C8D' };
}
