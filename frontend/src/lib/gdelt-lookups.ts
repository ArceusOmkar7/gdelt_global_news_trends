export const QUAD_CLASS_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'Verbal Cooperation',  color: '#00f3ff' },
  2: { label: 'Material Cooperation', color: '#00ff41' },
  3: { label: 'Verbal Conflict',      color: '#ffdc00' },
  4: { label: 'Material Conflict',    color: '#ff003c' },
};

export const CAMEO_ROOT_LABELS: Record<string, string> = {
  '01': 'Make Public Statement',
  '02': 'Appeal',
  '03': 'Express Intent to Cooperate',
  '04': 'Consult',
  '05': 'Engage in Diplomatic Cooperation',
  '06': 'Engage in Material Cooperation',
  '07': 'Provide Aid',
  '08': 'Yield',
  '09': 'Investigate',
  '10': 'Demand',
  '11': 'Disapprove',
  '12': 'Reject',
  '13': 'Threaten',
  '14': 'Protest',
  '15': 'Exhibit Military Posture',
  '16': 'Reduce Relations',
  '17': 'Coerce',
  '18': 'Assault',
  '19': 'Fight',
  '20': 'Use Unconventional Mass Violence',
};

export const ACTOR_TYPE_LABELS: Record<string, string> = {
  'GOV': 'Government',
  'MIL': 'Military',
  'REB': 'Rebel',
  'MED': 'Media',
  'NGO': 'NGO',
  'IGO': 'Intergovernmental Org',
  'CVL': 'Civilian',
  'OPP': 'Political Opposition',
  'BUS': 'Business',
  'CRM': 'Criminal',
  'UAF': 'Unaffiliated Armed Forces',
  'AGR': 'Agriculture',
  'EDU': 'Education',
  'ELI': 'Elite',
  'ENV': 'Environment',
  'HLH': 'Health',
  'LAB': 'Labor',
  'LEG': 'Legislature',
  'REL': 'Religion',
  'SOC': 'Social',
  'SPY': 'Intelligence',
  'JUD': 'Judiciary',
  'MOD': 'Moderate',
  'RAD': 'Radical',
  'REF': 'Refugee',
  'SET': 'Settler',
  'VET': 'Veteran',
};

export function cleanGkgTheme(raw: string): string {
  // Remove known prefixes (order matters — longer/more specific first)
  const prefixes = [
    'WB_\\d+_',
    'CRISISLEX_C\\d+_',
    'CRISISLEX_',
    'FNCACT_',
    'EPU_POLICY_',
    'EPU_',
    'SOC_',
    'ENV_',
    'ECON_',
    'MED_',
    'TAX_FNCACT_',
    'TAX_',
    'USPEC_',
    'UNGP_',
  ];
  let clean = raw;
  for (const prefix of prefixes) {
    clean = clean.replace(new RegExp(`^${prefix}`, 'i'), '');
  }
  return clean
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase());
}
