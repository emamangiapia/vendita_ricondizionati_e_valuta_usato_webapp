/** Palette originale dal tailwind.config.js di assistente_negozianti. */
export const brand = Object.freeze({
green:'#7CB518',greenDark:'#6A9B14',orange:'#E85D04',orangeDark:'#D14F00',
background:'#F5F5F5',white:'#FFFFFF',text:'#333333',textSecondary:'#666666',
textMuted:'#999999',footer:'#2D2D2D',blue:'#3B82F6',red:'#EF4444'
} as const);
/** Varianti piu' scure per contrasto accessibile su pulsanti. */
export const actions = Object.freeze({primary:'#4D7609',primaryHover:'#3F6206',
commerce:'#B84400',commerceHover:'#923700'} as const);
export const spacing = Object.freeze({xs:4,sm:8,md:12,lg:16,xl:24,xxl:32,xxxl:48} as const);
export const radius = Object.freeze({sm:6,md:8,lg:12,xl:16,pill:999} as const);
export const breakpoints = Object.freeze({mobile:640,tablet:900,desktop:1200} as const);