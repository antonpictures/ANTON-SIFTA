import React, { useState, useEffect, useCallback, useRef } from 'react';
import { GamePhase, Card as CardType, GambleHistoryItem } from './types';
import { PAY_TABLE, MAX_BET, MIN_BET, STARTING_CREDITS, MAX_GAMBLE_ATTEMPTS, ANTI_GAMBLING_MESSAGES, DEAL_AGAIN_MESSAGES, STREAK_LOSS_MESSAGES } from './constants';
import { createDeck, evaluateHand, getWinningCards, autoHoldStrategy } from './services/gameLogic';
import { playSound } from './services/soundService';
import PayTable from './components/PayTable';
import Card from './components/Card';
import GameInfo from './components/GameInfo';
import Controls from './components/Controls';
import Modal from './components/Modal';
import GambleView from './components/GambleView';
import HistoryLog from './components/HistoryLog';

const App: React.FC = () => {
    const [credits, setCredits] = useState<number>(STARTING_CREDITS);
    const [betAmount, setBetAmount] = useState<number>(250);
    const [currentWin, setCurrentWin] = useState<number>(0);
    const [hand, setHand] = useState<CardType[]>([]);
    const [heldCards, setHeldCards] = useState<boolean[]>([false, false, false, false, false]);
    const [winningCards, setWinningCards] = useState<boolean[]>([false, false, false, false, false]);
    const [phase, setPhase] = useState<GamePhase>(GamePhase.Betting);
    const [handResult, setHandResult] = useState<string>('');
    const [deck, setDeck] = useState<CardType[]>([]);
    const [showOutOfCreditsModal, setShowOutOfCreditsModal] = useState<boolean>(false);
    const [gambleAttempts, setGambleAttempts] = useState<number>(0);
    const [losingMessage, setLosingMessage] = useState<string>('');
    const [winMessage, setWinMessage] = useState<string>('');
    const [dealAgainText, setDealAgainText] = useState<string>('DEAL AGAIN');
    const [lastWin, setLastWin] = useState<{amount: number; result: string}>({amount: 0, result: ''});
    const [history, setHistory] = useState<GambleHistoryItem[]>([]);
    const [isPanelVisible, setIsPanelVisible] = useState(true);
    const [gambleWonCards, setGambleWonCards] = useState<CardType[]>([]);
    const [showMaxGambleWinModal, setShowMaxGambleWinModal] = useState<boolean>(false);
    const [maxGambleWinAmount, setMaxGambleWinAmount] = useState<number>(0);

    // Demo Mode State
    const [isDemoRunning, setIsDemoRunning] = useState<boolean>(true);
    const [demoMessage, setDemoMessage] = useState<string>("DEMO --- HOW TO PLAY");
    const [demoGambleGuess, setDemoGambleGuess] = useState<'red' | 'black' | null>(null);
    const [demoRevealedCard, setDemoRevealedCard] = useState<CardType | null>(null);
    const [isDealButtonFlashing, setIsDealButtonFlashing] = useState<boolean>(false);
    const demoTimeoutRef = useRef<number | null>(null);
    const isDemoRunningRef = useRef(isDemoRunning);
    isDemoRunningRef.current = isDemoRunning;


    useEffect(() => {
        try {
            const savedHistory = localStorage.getItem('STGMPokerGambleHistory');
            if (savedHistory) {
                setHistory(JSON.parse(savedHistory));
            }
        } catch (error) {
            console.error("Could not load gamble history:", error);
        }
    }, []);

    useEffect(() => {
        try {
            localStorage.setItem('STGMPokerGambleHistory', JSON.stringify(history));
        } catch (error) {
            console.error("Could not save gamble history:", error);
        }
    }, [history]);

    useEffect(() => {
        if (credits === 0 && betAmount === 0 && phase === GamePhase.Betting) {
            const randomMsg = ANTI_GAMBLING_MESSAGES[Math.floor(Math.random() * ANTI_GAMBLING_MESSAGES.length)];
            setLosingMessage(randomMsg);
        }
    }, [credits, betAmount, phase]);

    const transitionToPhase = useCallback((nextPhase: GamePhase, callback?: () => void) => {
        setIsPanelVisible(false);
        setTimeout(() => {
            setPhase(nextPhase);
            if (callback) callback();
            setIsPanelVisible(true);
        }, 250);
    }, []);

    const resetHand = useCallback((isDemo = false) => {
        if (!isDemo) {
            setHand([]); // Only clear the hand if it's NOT a demo reset, to prevent flicker.
        }
        setHeldCards([false, false, false, false, false]);
        setWinningCards([false, false, false, false, false]);
        setCurrentWin(0);
        setHandResult('');
        setLastWin({amount: 0, result: ''});
        setLosingMessage('');
        setWinMessage('');
        setGambleAttempts(0);
        setPhase(GamePhase.Betting);
        setDealAgainText('DEAL AGAIN');
        setGambleWonCards([]);
        if (!isDemo) {
            setDemoMessage("");
            setDemoGambleGuess(null);
            setDemoRevealedCard(null);
        }
    }, []);

    const stopDemoMode = useCallback(() => {
        if (isDemoRunningRef.current) {
            setIsDemoRunning(false);
            if (demoTimeoutRef.current) {
                clearTimeout(demoTimeoutRef.current);
            }
            resetHand(false);
            setIsDealButtonFlashing(true);
        }
    }, [resetHand]);
    
    useEffect(() => {
        const handleUserActivity = () => {
            if (isDemoRunningRef.current) {
                stopDemoMode();
            }
        };

        window.addEventListener('mousemove', handleUserActivity);
        window.addEventListener('mousedown', handleUserActivity);

        return () => {
            window.removeEventListener('mousemove', handleUserActivity);
            window.removeEventListener('mousedown', handleUserActivity);
        };
    }, [stopDemoMode]);

    const handleDeal = useCallback(() => {
        playSound('deal');
        stopDemoMode();
        setIsDealButtonFlashing(false);
        if (betAmount <= 0) {
            return;
        }
        if (credits < betAmount) {
            setShowOutOfCreditsModal(true);
            return;
        }

        setCredits(prev => prev - betAmount);
        const newDeck = createDeck();
        const newHand = newDeck.slice(0, 5);
        setHand(newHand);
        setDeck(newDeck.slice(5));
        setPhase(GamePhase.Dealt);
        setHandResult('');
        setLastWin({amount: 0, result: ''});
        setLosingMessage('');
        setWinMessage('');
        setCurrentWin(0);
        setWinningCards([false, false, false, false, false]);
        setHeldCards(autoHoldStrategy(newHand));
        setGambleWonCards([]);
    }, [credits, betAmount, stopDemoMode]);

    const handleDraw = useCallback(() => {
        playSound('deal');
        let deckIndex = 0;
        const finalHand = hand.map((card, i) => {
            if (!heldCards[i]) {
                return deck[deckIndex++];
            }
            return card;
        });

        setHand(finalHand);
        const result = evaluateHand(finalHand);
        setHandResult(result);

        const payout = PAY_TABLE[result] || 0;
        const winAmount = payout * betAmount;
        
        if (winAmount > 0) {
            playSound('win');
            setCurrentWin(winAmount);
            setWinningCards(getWinningCards(finalHand, result));
            setLosingMessage('');
            setLastWin({ amount: winAmount, result });
        } else {
            setLastWin({ amount: 0, result: 'NO WIN' });
        }
        
        setPhase(GamePhase.Drawn);
    }, [hand, heldCards, deck, betAmount]);
    
    const handleCashOut = useCallback(() => {
        playSound('click');
        if (currentWin > 0) {
            const randomMsg = ANTI_GAMBLING_MESSAGES[Math.floor(Math.random() * ANTI_GAMBLING_MESSAGES.length)];
            setWinMessage(randomMsg);
        }

        if (phase === GamePhase.Gamble) {
            transitionToPhase(GamePhase.Betting, () => {
                const newHistoryItem: GambleHistoryItem = {
                    id: Date.now().toString(),
                    outcome: 'cashed_out',
                    amount: currentWin,
                    streak: gambleAttempts,
                    timestamp: Date.now(),
                    wonCards: gambleWonCards,
                };
                setHistory(prev => [newHistoryItem, ...prev]);
                setCredits(prev => prev + currentWin);
                setCurrentWin(0);
                setGambleAttempts(0);
                setGambleWonCards([]);
            });
        } else {
            setCredits(prev => prev + currentWin);
            setCurrentWin(0);
            setPhase(GamePhase.Betting);
            setGambleAttempts(0);
        }
    }, [currentWin, phase, gambleAttempts, history, transitionToPhase, gambleWonCards]);

    const handleToggleHold = (index: number) => {
        playSound('hold');
        stopDemoMode();
        if (phase === GamePhase.Dealt) {
            setHeldCards(prev => {
                const newHeld = [...prev];
                newHeld[index] = !newHeld[index];
                return newHeld;
            });
        }
    };

    const handleBetChange = (direction: 'up' | 'down' | 'max') => {
        playSound('click');
        stopDemoMode();
        setIsDealButtonFlashing(false);
        if (direction === 'max') {
            setBetAmount(Math.min(MAX_BET, credits));
        } else if (direction === 'up') {
            setBetAmount(prev => Math.min(MAX_BET, prev * 2 > credits ? credits : prev * 2));
        } else {
            setBetAmount(prev => Math.max(MIN_BET, Math.floor(prev / 2)));
        }
    };
    
    const handleGambleResult = useCallback((isWin: boolean, card: CardType) => {
        if (isWin) {
            playSound('gambleWin');
            setGambleWonCards(prev => [...prev, card]);
            const newAttempts = gambleAttempts + 1;
            setGambleAttempts(newAttempts);
            setCurrentWin(prevWin => {
                const newWin = prevWin * 2;
                if (newAttempts >= MAX_GAMBLE_ATTEMPTS) {
                    setTimeout(() => {
                         transitionToPhase(GamePhase.Betting, () => {
                            const newHistoryItem: GambleHistoryItem = {
                                id: Date.now().toString(),
                                outcome: 'cashed_out',
                                amount: newWin,
                                streak: newAttempts,
                                timestamp: Date.now(),
                                wonCards: [...gambleWonCards, card],
                            };
                            setHistory(prev => [newHistoryItem, ...prev]);
                            setCredits(prevCredits => prevCredits + newWin);
                            setCurrentWin(0);
                            setGambleAttempts(0);
                            setGambleWonCards([]);
                            setMaxGambleWinAmount(newWin);
                            setShowMaxGambleWinModal(true);
                         });
                    }, 1500);
                }
                return newWin;
            });
        } else {
            playSound('gambleLose');
            transitionToPhase(GamePhase.Drawn, () => {
                const streakLength = gambleAttempts + 1;
                const newHistoryItem: GambleHistoryItem = {
                    id: Date.now().toString(),
                    outcome: 'lost',
                    amount: currentWin,
                    streak: streakLength,
                    timestamp: Date.now(),
                    wonCards: gambleWonCards,
                    finalCard: card,
                };
                setHistory(prev => [newHistoryItem, ...prev]);
                setCurrentWin(0);
                
                const messagePool = STREAK_LOSS_MESSAGES[streakLength] || ANTI_GAMBLING_MESSAGES;
                const randomMsg = messagePool[Math.floor(Math.random() * messagePool.length)];
                setLosingMessage(randomMsg);

                const randomBtnText = DEAL_AGAIN_MESSAGES[Math.floor(Math.random() * DEAL_AGAIN_MESSAGES.length)];
                setDealAgainText(randomBtnText);
                setGambleWonCards([]);
            });
        }
    }, [gambleAttempts, currentWin, transitionToPhase, gambleWonCards]);

    const reloadCredits = () => {
        playSound('click');
        setCredits(STARTING_CREDITS);
        setBetAmount(250);
        setShowOutOfCreditsModal(false);
        resetHand();
    };

    useEffect(() => {
        if (phase === GamePhase.Drawn && currentWin === 0 && !isDemoRunning) {
            const timeoutId = setTimeout(() => {
                if (credits >= betAmount && betAmount > 0) {
                    handleDeal();
                } else {
                    if (credits === 0) {
                        setShowOutOfCreditsModal(true);
                    } else if (betAmount > credits) {
                        setBetAmount(credits); // Auto-adjust bet if credits are low but not zero
                    }
                    resetHand();
                }
            }, 3000);
            return () => clearTimeout(timeoutId);
        }
    }, [phase, currentWin, credits, betAmount, handleDeal, resetHand, isDemoRunning]);

    useEffect(() => {
        if (!isDemoRunning) return;
    
        const runDemoGamble = (currentGambleWin: number, attempt: number, wonCards: CardType[]) => {
            if (!isDemoRunningRef.current || attempt > 2) { // Limit demo gamble streak to 2
                setDemoMessage("DEMO --- COLLECTING THE WIN!");
                demoTimeoutRef.current = window.setTimeout(() => runDemoCycle(true), 2500);
                return;
            }
    
            transitionToPhase(GamePhase.Gamble);
            setDemoMessage("DEMO --- DOUBLE OR NOTHING...");
            
            demoTimeoutRef.current = window.setTimeout(() => {
                if (!isDemoRunningRef.current) return;
                const guess = Math.random() > 0.5 ? 'red' : 'black';
                setDemoMessage(`DEMO --- GUESSING ${guess.toUpperCase()}!`);
                setDemoGambleGuess(guess);
    
                const card = createDeck()[0];
                setDemoRevealedCard(card);
                
                const isRed = card.suit === '♥' || card.suit === '♦';
                const isWin = (guess === 'red' && isRed) || (guess === 'black' && !isRed);
    
                demoTimeoutRef.current = window.setTimeout(() => {
                    if (!isDemoRunningRef.current) return;
                    setDemoGambleGuess(null);
                    setDemoRevealedCard(null);
    
                    if (isWin) {
                        const newWin = currentGambleWin * 2;
                        const newWonCards = [...wonCards, card];
                        setDemoMessage("DEMO --- WIN! LET'S GO AGAIN!");
                        setCurrentWin(newWin);
                        setGambleWonCards(newWonCards);
                        demoTimeoutRef.current = window.setTimeout(() => runDemoGamble(newWin, attempt + 1, newWonCards), 2500);
                    } else {
                        setDemoMessage("DEMO --- LOST THE GAMBLE!");
                        transitionToPhase(GamePhase.Betting, () => {
                           setCurrentWin(0);
                           demoTimeoutRef.current = window.setTimeout(() => runDemoCycle(true), 2500);
                        });
                    }
                }, 2500);
            }, 2500);
        };
    
        const runDemoCycle = (isRestarting = false) => {
            if (isRestarting) {
                resetHand(true);
            }
    
            setDemoMessage("DEMO --- DEALING A NEW HAND");
            const newDeck = createDeck();
            let currentDeck = [...newDeck];
            const newHand = currentDeck.splice(0, 5);
            setHand(newHand);
            setPhase(GamePhase.Dealt);
            const holds = autoHoldStrategy(newHand);
            setHeldCards(holds);
            
            demoTimeoutRef.current = window.setTimeout(() => {
                if (!isDemoRunningRef.current) return;
                setDemoMessage("DEMO --- HOLDING PROMISING CARDS...");
    
                const finalHand = newHand.map((card, i) => holds[i] ? card : currentDeck.shift()!);
                setHand(finalHand);
                const result = evaluateHand(finalHand);
                setHandResult(result);
                setPhase(GamePhase.Drawn);
                const payout = PAY_TABLE[result] || 0;
                const winAmount = payout * betAmount;
                
                demoTimeoutRef.current = window.setTimeout(() => {
                    if (!isDemoRunningRef.current) return;
    
                    if (winAmount > 0) {
                        setCurrentWin(winAmount);
                        setWinningCards(getWinningCards(finalHand, result));
                        setLastWin({ amount: winAmount, result });
                        setDemoMessage(`DEMO --- A ${result.toUpperCase()}!`);
                        
                        const shouldGamble = Math.random() > 0.4; // 60% chance to gamble
                        if (shouldGamble) {
                            demoTimeoutRef.current = window.setTimeout(() => runDemoGamble(winAmount, 1, []), 3000);
                        } else {
                            setDemoMessage("DEMO --- TAKING THE WIN.");
                            demoTimeoutRef.current = window.setTimeout(() => runDemoCycle(true), 3000);
                        }
                    } else {
                        setLastWin({ amount: 0, result: 'NO WIN' });
                        setDemoMessage("DEMO --- UNLUCKY. TRYING AGAIN.");
                        demoTimeoutRef.current = window.setTimeout(() => runDemoCycle(true), 3000);
                    }
                }, 2500);
            }, 2500);
        };
    
        runDemoCycle();
    
        return () => {
            if (demoTimeoutRef.current) clearTimeout(demoTimeoutRef.current);
        };
    }, [isDemoRunning, betAmount, transitionToPhase]);

    const closeMaxGambleModal = () => {
        playSound('click');
        setShowMaxGambleWinModal(false);
    };

    return (
        <div className="min-h-screen text-white flex flex-col items-center p-1 sm:p-2 selection:bg-brand-yellow selection:text-black">
            <main className="w-full max-w-md mx-auto flex flex-col items-center">
                <header className="w-full flex flex-col sm:flex-row justify-between sm:items-center px-1 text-center sm:text-left">
                    <h1 className="text-lg font-bold text-slate-300 tracking-wider mb-2 sm:mb-0">$STGM Google Maps Video Poker</h1>
                    <GameInfo credits={credits} betAmount={betAmount} currentWin={currentWin} />
                </header>

                <div className="w-full bg-black rounded-2xl shadow-lg">
                    <div className={`w-full min-h-[18rem] flex items-center justify-center transition-opacity duration-200 ease-in-out ${isPanelVisible ? 'opacity-100' : 'opacity-0'}`}>
                         {phase === GamePhase.Gamble ? (
                            <GambleView 
                                currentWin={currentWin}
                                onGambleResult={handleGambleResult}
                                onCashOut={handleCashOut}
                                wonCards={gambleWonCards}
                                demoGuess={demoGambleGuess}
                                demoRevealedCard={demoRevealedCard}
                            />
                         ) : (
                            <PayTable betAmount={betAmount} handResult={handResult} />
                         )}
                    </div>
                    {phase !== GamePhase.Gamble && (
                        <Controls 
                            phase={phase}
                            credits={credits}
                            betAmount={betAmount}
                            currentWin={currentWin}
                            onDeal={handleDeal}
                            onDraw={handleDraw}
                            onBetChange={handleBetChange}
                            onCashOut={handleCashOut}
                            onGamble={() => { playSound('click'); transitionToPhase(GamePhase.Gamble); }}
                            dealAgainText={dealAgainText}
                            isDealButtonFlashing={isDealButtonFlashing}
                        />
                    )}
                </div>
                
                <div className="w-full min-h-[1.75rem] flex items-center justify-center">
                    {lastWin.amount > 0 && phase !== GamePhase.Betting ? (
                         <div key={lastWin.result} className="bg-brand-green text-white text-sm font-bold px-4 py-1.5 rounded-full shadow-lg animate-pop-in">
                            {lastWin.result}
                        </div>
                    ) : winMessage ? (
                        <div className="bg-black/50 border border-brand-green/50 px-4 py-2 rounded-xl animate-pop-in">
                            <p className="text-base text-yellow-300 text-center">
                                {winMessage}
                            </p>
                        </div>
                    ) : currentWin === 0 && losingMessage ? (
                        <div className="bg-black/50 border border-brand-red/50 px-4 py-2 rounded-xl animate-pop-in">
                            <p className="text-base text-yellow-300 text-center">
                                {losingMessage}
                            </p>
                        </div>
                    ) : null}
                </div>


                <div className="w-full min-h-[13rem] flex items-center justify-center">
                    {hand.length === 5 ? (
                         <div className="flex justify-center space-x-1 sm:space-x-2">
                            {hand.map((card, i) => (
                                <Card
                                    key={`${card.suit}-${card.value}-${i}`}
                                    card={card}
                                    isHeld={heldCards[i]}
                                    isWinning={winningCards[i]}
                                    isDealtPhase={phase === GamePhase.Dealt && !isDemoRunning}
                                    onClick={() => handleToggleHold(i)}
                                    animationDelay={i * 80}
                                />
                            ))}
                        </div>
                    ) : (
                         <div className="text-center px-4">
                            <p className="text-2xl font-bold text-slate-400 tracking-wide animate-pulse">
                                {isDemoRunning ? demoMessage : 'Powered by Google Maps $STGM on Solana'}
                            </p>
                        </div>
                    )}
                </div>
                
                <HistoryLog history={history} />
            </main>
            
            <Modal
                isOpen={showOutOfCreditsModal}
                onClose={() => {}}
                title="It's Time To Stop."
            >
                <div className="text-center">
                    <p className="text-lg text-slate-300">You've run out of credits. This feeling of loss is what addiction feeds on.</p>
                    <p className="mb-6 text-slate-300">In the real world, there are no restarts. If gambling is a problem, seek help.</p>
                    <button 
                        onClick={reloadCredits}
                        className="w-full bg-brand-yellow text-brand-dark-bg font-bold py-3 px-6 rounded-xl hover:opacity-90 transition-opacity duration-200"
                    >
                        Restart Simulation
                    </button>
                </div>
            </Modal>
            
            <Modal
                isOpen={showMaxGambleWinModal}
                onClose={closeMaxGambleModal}
                title="MAX STREAK!"
            >
                <div className="text-center">
                    <p className="text-3xl text-brand-yellow font-bold mb-4">
                        You won {maxGambleWinAmount.toLocaleString()} $STGM!
                    </p>
                    <p className="text-lg text-slate-300 mb-6">You degenerate gambler. ;)</p>
                    <button 
                        onClick={closeMaxGambleModal}
                        className="w-full bg-brand-yellow text-brand-dark-bg font-bold py-3 px-6 rounded-xl hover:opacity-90 transition-opacity duration-200"
                    >
                        Awesome
                    </button>
                </div>
            </Modal>
        </div>
    );
};

export default App;