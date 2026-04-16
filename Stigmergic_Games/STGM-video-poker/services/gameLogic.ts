
import { Card } from '../types';
import { SUITS, VALUES, CARD_VALUE_MAP } from '../constants';

export const createDeck = (): Card[] => {
    const deck: Card[] = [];
    for (const suit of SUITS) {
        for (const value of VALUES) {
            deck.push({ suit, value });
        }
    }
    return shuffleDeck(deck);
};

const shuffleDeck = (deck: Card[]): Card[] => {
    const newDeck = [...deck];
    for (let i = newDeck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [newDeck[i], newDeck[j]] = [newDeck[j], newDeck[i]];
    }
    return newDeck;
};

export const evaluateHand = (hand: Card[]): string => {
    if (hand.length < 5) return "High Card";

    const valueCounts: { [key: string]: number } = {};
    hand.forEach(card => {
        valueCounts[card.value] = (valueCounts[card.value] || 0) + 1;
    });

    const isFlush = new Set(hand.map(c => c.suit)).size === 1;
    const sortedValues = hand.map(c => CARD_VALUE_MAP[c.value]).sort((a, b) => a - b);
    
    const isAceLowStraight = JSON.stringify(sortedValues) === JSON.stringify([2,3,4,5,14]);
    let isNormalStraight = true;
    for (let i = 0; i < sortedValues.length - 1; i++) {
        if (sortedValues[i+1] !== sortedValues[i] + 1) {
            isNormalStraight = false;
            break;
        }
    }
    const isStraight = isNormalStraight || isAceLowStraight;

    if (isStraight && isFlush && sortedValues.includes(14) && sortedValues.includes(13)) return "Royal Flush";
    if (isStraight && isFlush) return "Straight Flush";

    const counts = Object.values(valueCounts).sort((a,b) => b-a);
    if (counts[0] === 4) return "Four of a Kind";
    if (counts[0] === 3 && counts[1] === 2) return "Full House";
    if (isFlush) return "Flush";
    if (isStraight) return "Straight";
    if (counts[0] === 3) return "Three of a Kind";
    if (counts[0] === 2 && counts[1] === 2) return "Two Pair";

    const pairs = Object.entries(valueCounts).filter(([, count]) => count === 2);
    if (pairs.length === 1) {
        const pairValue = CARD_VALUE_MAP[pairs[0][0] as keyof typeof CARD_VALUE_MAP];
        if (pairValue >= 11) return "Jacks or Better";
    }

    return "High Card";
};

export const getWinningCards = (hand: Card[], handResult: string): boolean[] => {
    const winning = new Array(5).fill(false);
    if (hand.length < 5 || handResult === "High Card") return winning;

    const valueCounts: { [key: string]: number[] } = {};
    hand.forEach((card, index) => {
        if (!valueCounts[card.value]) valueCounts[card.value] = [];
        valueCounts[card.value].push(index);
    });

    switch (handResult) {
        case "Royal Flush":
        case "Straight Flush":
        case "Flush":
        case "Straight":
            return new Array(5).fill(true);

        case "Four of a Kind":
        case "Three of a Kind":
        case "Full House":
        case "Two Pair":
        case "Jacks or Better":
            const resultCounts = evaluateHandCounts(handResult);
            Object.keys(valueCounts).forEach(value => {
                if (resultCounts.includes(valueCounts[value].length)) {
                     if (handResult === "Jacks or Better") {
                        if (CARD_VALUE_MAP[value as keyof typeof CARD_VALUE_MAP] >= 11) {
                            valueCounts[value].forEach(i => winning[i] = true);
                        }
                    } else {
                        valueCounts[value].forEach(i => winning[i] = true);
                    }
                }
            });
            break;
    }
    return winning;
};

const evaluateHandCounts = (handResult: string): number[] => {
    switch (handResult) {
        case "Four of a Kind": return [4];
        case "Full House": return [3, 2];
        case "Three of a Kind": return [3];
        case "Two Pair": return [2];
        case "Jacks or Better": return [2];
        default: return [];
    }
};

export const autoHoldStrategy = (hand: Card[]): boolean[] => {
    const hold = new Array(5).fill(false);
    if (hand.length < 5) return hold;
    
    const result = evaluateHand(hand);
    if (result !== "High Card") {
        return getWinningCards(hand, result);
    }
    
    // Check for 4 to a Royal Flush
    // This part can be complex, for this version we'll keep it simple
    // and just hold made hands or high pairs.

    // A more advanced strategy could check for 4 to a flush, 4 to a straight, etc.
    // For now, if no made hand, we discard all. A low pair is held by getWinningCards/evaluateHand
    // if `evaluateHand` is modified to return "Low Pair". But current spec is Jacks or Better.
    
    return hold;
};
