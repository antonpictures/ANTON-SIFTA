
// FIX: Removed circular import. The 'Card' type is defined in this file and does not need to be imported.
export type Suit = '♠' | '♥' | '♦' | '♣';
export type Value = '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | '10' | 'J' | 'Q' | 'K' | 'A';

export interface Card {
    suit: Suit;
    value: Value;
}

export enum GamePhase {
    Betting = 'betting',
    Dealt = 'dealt',
    Drawn = 'drawn',
    Gamble = 'gamble',
}

export interface GambleHistoryItem {
    id: string;
    outcome: 'cashed_out' | 'lost';
    amount: number;
    streak: number;
    timestamp: number;
    finalCard?: Card;
    wonCards?: Card[];
}
