import React, { useState } from 'react';
import { createDeck } from '../services/gameLogic';
import { Card as CardType } from '../types';
import { playSound } from '../services/soundService';
import Card from './Card';

interface GambleViewProps {
    currentWin: number;
    onGambleResult: (isWin: boolean, card: CardType) => void;
    onCashOut: () => void;
    wonCards: CardType[];
    demoGuess?: 'red' | 'black' | null;
    demoRevealedCard?: CardType | null;
}

const GambleView: React.FC<GambleViewProps> = ({ currentWin, onGambleResult, onCashOut, wonCards, demoGuess, demoRevealedCard }) => {
    const [revealedCard, setRevealedCard] = useState<CardType | null>(null);
    const [guess, setGuess] = useState<'red' | 'black' | null>(null);
    const [isRevealing, setIsRevealing] = useState(false);

    const isDemoActive = !!demoRevealedCard;

    const handleGuess = (color: 'red' | 'black') => {
        if (isRevealing || isDemoActive) return;
        playSound('click');
        setIsRevealing(true);
        setGuess(color);

        const card = createDeck()[0];
        setRevealedCard(card);

        const isRed = card.suit === '♥' || card.suit === '♦';
        const isCorrect = (color === 'red' && isRed) || (color === 'black' && !isRed);

        setTimeout(() => {
            onGambleResult(isCorrect, card);
            setIsRevealing(false);
            setRevealedCard(null);
            setGuess(null);
        }, 1500);
    };

    const cardToShow = demoRevealedCard || revealedCard;
    const buttonsDisabled = isRevealing || isDemoActive;

    return (
        <div className="bg-brand-panel-bg rounded-2xl p-3 shadow-lg flex flex-col justify-around items-center h-full w-full">
            <div className="text-center text-white">
                <h2 className="text-lg font-semibold tracking-wider">DOUBLE OR NOTHING</h2>
                <p className="text-sm text-slate-300">Current: {currentWin.toLocaleString()}</p>
                <p className="text-base font-bold text-brand-yellow">Double to: {(currentWin * 2).toLocaleString()}</p>
            </div>

            <div className="flex flex-col items-center">
                 <div className="flex justify-center items-center h-10 space-x-1 mb-2">
                    {wonCards.map((card, index) => {
                        const isRed = card.suit === '♥' || card.suit === '♦';
                        return (
                            <div 
                                key={index} 
                                className={`w-6 h-9 rounded-sm flex items-center justify-center text-white font-bold text-lg shadow-inner
                                            ${isRed ? 'bg-brand-red' : 'bg-black'}`}
                            >
                                {card.suit}
                            </div>
                        );
                    })}
                </div>
                <div className="flex justify-center items-center h-36">
                    {cardToShow ? (
                        <Card card={cardToShow} isHeld={false} isWinning={false} isDealtPhase={false} onClick={() => {}} animationDelay={0} />
                    ) : (
                        <div className="w-24 h-36 bg-brand-dark-bg/70 border-2 border-brand-panel-light border-dashed rounded-xl flex justify-center items-center">
                            <span className="text-4xl text-brand-panel-light font-bold">?</span>
                        </div>
                    )}
                </div>
            </div>

            <div className="w-full flex flex-col space-y-2">
                <p className="text-center text-sm text-slate-300 font-semibold tracking-wider">CHOOSE COLOR</p>
                <div className="flex space-x-2">
                    <button
                        onClick={() => handleGuess('red')}
                        disabled={buttonsDisabled}
                        className={`w-full h-12 text-base font-bold rounded-xl transition-all duration-200 disabled:opacity-50
                            bg-brand-red hover:opacity-90 disabled:bg-brand-red
                            ${(guess === 'red' && isRevealing) || demoGuess === 'red' ? 'ring-4 ring-offset-2 ring-offset-brand-panel-bg ring-white' : ''}`}
                    >
                        RED
                    </button>
                    <button
                        onClick={() => handleGuess('black')}
                        disabled={buttonsDisabled}
                        className={`w-full h-12 text-base font-bold rounded-xl transition-all duration-200 disabled:opacity-50
                            bg-black text-white hover:bg-black/80 disabled:bg-black
                            ${(guess === 'black' && isRevealing) || demoGuess === 'black' ? 'ring-4 ring-offset-2 ring-offset-brand-panel-bg ring-white' : ''}`}
                    >
                        BLACK
                    </button>
                </div>

                <button
                    onClick={onCashOut}
                    disabled={buttonsDisabled}
                    className="w-full bg-brand-panel-light text-white font-semibold py-3 px-8 rounded-xl hover:opacity-90 transition-colors duration-200 disabled:opacity-50"
                >
                    CASH OUT
                </button>
            </div>
        </div>
    );
};

export default GambleView;