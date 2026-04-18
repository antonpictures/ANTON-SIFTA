import { Suit, Value } from './types';

export const SUITS: Suit[] = ['♠', '♥', '♦', '♣'];
export const VALUES: Value[] = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];

export const PAY_TABLE: { [key: string]: number } = {
    "Royal Flush": 800,
    "Straight Flush": 50,
    "Four of a Kind": 25,
    "Full House": 9,
    "Flush": 6,
    "Straight": 4,
    "Three of a Kind": 3,
    "Two Pair": 2,
    "Jacks or Better": 1,
};

export const PAY_TABLE_ORDER: string[] = [
    "Royal Flush", "Straight Flush", "Four of a Kind", "Full House", "Flush",
    "Straight", "Three of a Kind", "Two Pair", "Jacks or Better"
];

export const CARD_VALUE_MAP: { [key in Value]: number } = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
};

export const STARTING_CREDITS = 1000;
export const MAX_BET = 1000;
export const MIN_BET = 10;
export const MAX_GAMBLE_ATTEMPTS = 5;

export const ANTI_GAMBLING_MESSAGES: string[] = [
    "Remember, it's only a problem if you're losing.",
    "My financial plan? This. Right here.",
    "They say quitters never win, but I'm not seeing a lot of winning here either.",
    "This isn't an addiction. It's a dedicated pursuit of poverty.",
    "The odds are 50/50: you either win, or you explain where the money went.",
    "Who needs savings when you have 'potential'?",
    "I'm not chasing losses, I'm giving my money a chance to come back home.",
    "Don't worry, you can always win it back. (Narrator: He could not.)",
    "The thrill of the win is great, but crushing despair builds character.",
    "It's called 'risk management'.",
    "Statistically, you're bound to hit a royal flush. It might just cost you a house.",
    "You miss 100% of the bets you don't take. And also about 98% of the ones you do.",
    "99% of gamblers quit right before they're about to hit it big. Don't be a statistic.",
    "Is this rock bottom? No, I can still hear digging.",
    "I have a system. It's not a *winning* system, but it is a system.",
    "It's not a gambling problem, it's a gambling solution. To the problem of having too much money.",
    "Due for a win. Any minute now...",
    "This is my retirement fund. I'm retiring to a life of excitement and ramen.",
    "My therapist said I need to face my problems. So here I am.",
    "It's an investment in entertainment. Expensive, short-lived entertainment.",
    "Just think of it as a donation to the casino's light bill.",
    "One day, my kids will understand why their college fund is invested in video poker.",
];

export const STREAK_LOSS_MESSAGES: { [key: number]: string[] } = {
    1: [
        "Fell at the first hurdle. Classic.",
        "Doubled your money to... zero. Nice.",
        "That was a quick ride.",
        "You had a 50/50 shot. And you missed.",
    ],
    2: [
        "So close to 4x, yet so far.",
        "Greed is a powerful motivator. And a terrible financial advisor.",
        "You flew too close to the sun, Icarus.",
        "Should've cashed out.",
    ],
    3: [
        "8x was just a dream. This is reality.",
        "That one's gonna sting for a while.",
        "From hero to zero at lightning speed.",
        "You were on a roll. Past tense.",
    ],
    4: [
        "Risked it all for 16x and got nothing. Bold strategy.",
        "The house always wins. Especially on streak 4.",
        "So much potential... gone.",
        "This is how villains are made.",
    ],
    5: [
        "You were one guess away from glory. ONE.",
        "The ultimate choke. You could have been a legend.",
        "Maximum risk, zero reward. Perfect.",
        "This will be a tough one to forget.",
    ]
};

export const DEAL_AGAIN_MESSAGES: string[] = [
    "DEAL AGAIN",
    "CHASE LOSSES",
    "JUST ONE MORE",
    "WIN IT BACK",
    "THIS IS THE ONE",
    "MY LUCK'S TURNING",
    "IT'S FINE",
];