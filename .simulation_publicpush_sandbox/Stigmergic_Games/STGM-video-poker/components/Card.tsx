import React from 'react';
import { Card as CardType } from '../types';

interface CardProps {
    card: CardType;
    isHeld: boolean;
    isWinning: boolean;
isDealtPhase: boolean;
    onClick: () => void;
    animationDelay: number;
}

const Card: React.FC<CardProps> = ({ card, isHeld, isWinning, isDealtPhase, onClick, animationDelay }) => {
    const isRed = card.suit === '♥' || card.suit === '♦';

    const cardClasses = `
        relative w-20 h-28 sm:w-24 sm:h-36
        rounded-lg border shadow-card
        flex flex-col justify-between p-1 sm:p-2 font-bold select-none
        transition-all duration-300 ease-in-out
        overflow-hidden
        bg-white
        animate-deal-in
        ${isDealtPhase ? 'cursor-pointer hover:-translate-y-2' : ''}
        ${isWinning ? 'shadow-card-win-glow border-brand-green border-2 animate-win-pulse' : (isHeld ? 'shadow-card-held border-brand-yellow' : 'border-gray-300')}
    `;

    const bannerClasses = `
        absolute bottom-0 left-1/2 -translate-x-1/2 w-full text-center
        py-0.5 text-xs sm:text-sm font-semibold tracking-wide rounded-b-md
    `;
    
    const suitColorClass = isRed ? 'text-brand-red' : 'text-black';
    const valueColorClass = 'text-black';

    return (
        <div 
            className={cardClasses} 
            onClick={onClick}
            style={{ animationDelay: `${animationDelay}ms` }}
        >
            {isHeld && !isWinning && (
                <div className={`${bannerClasses} bg-brand-yellow text-black`}>
                    HELD
                </div>
            )}
            {isWinning && (
                <div className={`${bannerClasses} bg-brand-green text-white`}>
                    WIN
                </div>
            )}
            
            <div className={`text-left text-lg sm:text-xl ${valueColorClass}`}>
                <span>{card.value}</span>
                <span className={suitColorClass}>{card.suit}</span>
            </div>
            
            <div className={`text-center text-3xl sm:text-4xl ${suitColorClass}`}>
                {card.suit}
            </div>
            
            <div className="h-7" />
        </div>
    );
};

export default Card;