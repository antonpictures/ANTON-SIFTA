// A mapping of sound names to their respective audio file URLs.
const SOUND_URLS = {
    deal: 'https://cdn.pixabay.com/audio/2022/03/10/audio_2d067c28b5.mp3',
    hold: 'https://cdn.pixabay.com/audio/2022/03/15/audio_e927c65a94.mp3',
    win: 'https://cdn.pixabay.com/audio/2022/11/19/audio_2c8b09332e.mp3',
    gambleWin: 'https://cdn.pixabay.com/audio/2022/10/29/audio_206975a52a.mp3',
    gambleLose: 'https://cdn.pixabay.com/audio/2022/03/10/audio_e4a3c10f82.mp3',
    click: 'https://cdn.pixabay.com/audio/2022/03/15/audio_e927c65a94.mp3',
};

// Define a type for the sound names based on the keys of SOUND_URLS.
type SoundName = keyof typeof SOUND_URLS;

// A cache to store preloaded HTMLAudioElement objects for each sound.
const audioCache: { [key in SoundName]?: HTMLAudioElement } = {};

/**
 * Preloads all the sounds defined in SOUND_URLS.
 * This creates an Audio object for each sound and sets it to preload,
 * which helps in reducing latency when the sound is played for the first time.
 */
Object.keys(SOUND_URLS).forEach(key => {
    const soundName = key as SoundName;
    const audio = new Audio(SOUND_URLS[soundName]);
    audio.preload = 'auto';
    audioCache[soundName] = audio;
});

/**
 * Plays a sound by its name.
 * @param {SoundName} soundName - The name of the sound to play.
 */
export const playSound = (soundName: SoundName) => {
    const audio = audioCache[soundName];
    if (audio) {
        // Reset the audio's current time to 0 to allow for rapid, overlapping plays.
        audio.currentTime = 0;
        // Play the sound and catch any potential errors (e.g., browser autoplay restrictions).
        audio.play().catch(error => console.error(`Error playing sound: ${soundName}`, error));
    }
};
