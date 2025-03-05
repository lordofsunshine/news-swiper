document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.news-container');
    const cards = Array.from(document.querySelectorAll('.news-card'));
    const dots = Array.from(document.querySelectorAll('.swipe-dot'));
    const progress = document.querySelector('.progress');
    
    let currentIndex = 0;
    let startY = 0;
    let currentY = 0;
    let isDragging = false;
    let isLoading = false;
    let currentPage = 1;
    let autoProgressInterval;
    let lastInteractionTime = Date.now();
    
    function startProgress() {
        if (autoProgressInterval) {
            clearInterval(autoProgressInterval);
        }
        
        progress.style.width = '0%';
        const startTime = Date.now();
        const duration = 10000; 
        
        autoProgressInterval = setInterval(() => {
            if (Date.now() - lastInteractionTime < 1000) {
                return;
            }
            
            const elapsed = Date.now() - startTime;
            const percentage = (elapsed / duration) * 100;
            
            if (percentage >= 100) {
                showNext();
            } else {
                progress.style.width = percentage + '%';
            }
        }, 100);
    }
    
    function updateCards() {
        requestAnimationFrame(() => {
            cards.forEach((card, index) => {
                const diff = index - currentIndex;
                card.className = 'news-card';
                
                if (diff === 0) {
                    card.classList.add('active');
                } else if (diff < 0) {
                    card.classList.add('prev');
                } else {
                    card.classList.add('next');
                }
            });
            
            dots.forEach((dot, index) => {
                dot.classList.toggle('active', index === currentIndex);
            });
            
            if (cards[currentIndex]) {
                const url = cards[currentIndex].dataset.url;
                markArticleAsViewed(url);
            }
            
            startProgress();
        });
    }
    
    async function loadMoreNews() {
        if (isLoading) return;
        
        try {
            isLoading = true;
            const response = await fetch('/api/load-more', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ page: currentPage + 1 })
            });
            
            const data = await response.json();
            
            if (data.articles && data.articles.length > 0) {
                currentPage++;
                
                data.articles.forEach(article => {
                    const card = createNewsCard(article);
                    container.appendChild(card);
                });
                
                cards.push(...Array.from(container.querySelectorAll('.news-card:not([data-initialized])')));
                cards.forEach(card => card.dataset.initialized = 'true');
                
                const dotsContainer = document.querySelector('.swipe-indicator');
                data.articles.forEach(() => {
                    const dot = document.createElement('div');
                    dot.className = 'swipe-dot';
                    dotsContainer.appendChild(dot);
                });
                
                dots.push(...Array.from(document.querySelectorAll('.swipe-dot:not([data-initialized])')));
                dots.forEach(dot => dot.dataset.initialized = 'true');
            }
        } catch (error) {
            console.error('Error loading more news:', error);
        } finally {
            isLoading = false;
        }
    }
    
    function createNewsCard(article) {
        const card = document.createElement('div');
        card.className = 'news-card next';
        card.dataset.url = article.url;
        
        const content = `
            ${article.urlToImage ? `<div class="news-image" style="background-image: url('${article.urlToImage}')"></div>` : ''}
            <div class="news-content">
                <div style="width: 80%;">
                    <div class="source">${article.source.name || 'Новость'}</div>
                    <h2>${article.title}</h2>
                    <p>${article.description}</p>
                    <a href="${article.url}" target="_blank" class="read-more">Читать далее</a>
                </div>
            </div>
        `;
        
        card.innerHTML = content;
        return card;
    }
    
    async function markArticleAsViewed(url) {
        try {
            await fetch('/api/mark-viewed', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url })
            });
        } catch (error) {
            console.error('Error marking article as viewed:', error);
        }
    }
    
    function showNext() {
        lastInteractionTime = Date.now();
        
        if (currentIndex < cards.length - 1) {
            currentIndex++;
            updateCards();
        } else {
            loadMoreNews();
        }
    }
    
    function showPrev() {
        lastInteractionTime = Date.now();
        
        if (currentIndex > 0) {
            currentIndex--;
            updateCards();
        }
    }
    
    function handleTouchStart(e) {
        startY = e.type === 'mousedown' ? e.clientY : e.touches[0].clientY;
        isDragging = true;
        lastInteractionTime = Date.now();
    }
    
    function handleTouchMove(e) {
        if (!isDragging) return;
        
        e.preventDefault();
        currentY = e.type === 'mousemove' ? e.clientY : e.touches[0].clientY;
        const diff = currentY - startY;
        
        if ((currentIndex === 0 && diff > 0) || 
            (currentIndex === cards.length - 1 && diff < 0)) {
            return;
        }
        
        requestAnimationFrame(() => {
            cards.forEach((card, index) => {
                const offset = index - currentIndex;
                const translateY = diff + offset * window.innerHeight;
                card.style.transform = `translateY(${translateY}px)`;
            });
        });
    }
    
    function handleTouchEnd() {
        if (!isDragging) return;
        
        isDragging = false;
        const diff = currentY - startY;
        const threshold = window.innerHeight * 0.2;
        
        requestAnimationFrame(() => {
            cards.forEach(card => {
                card.style.transform = '';
                card.style.transition = 'transform 0.5s cubic-bezier(0.65, 0, 0.35, 1)';
            });
            
            if (Math.abs(diff) > threshold) {
                if (diff > 0 && currentIndex > 0) {
                    showPrev();
                } else if (diff < 0 && currentIndex < cards.length - 1) {
                    showNext();
                } else {
                    updateCards();
                }
            } else {
                updateCards();
            }
        });
    }
    
    const throttledTouchMove = throttle(handleTouchMove, 16);
    
    container.addEventListener('mousedown', handleTouchStart, { passive: true });
    window.addEventListener('mousemove', throttledTouchMove);
    window.addEventListener('mouseup', handleTouchEnd);
    
    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', throttledTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd);
    
    const throttledWheel = throttle((e) => {
        e.preventDefault();
        if (!isDragging) {
            if (e.deltaY > 0) {
                showNext();
            } else {
                showPrev();
            }
        }
    }, 16);
    
    container.addEventListener('wheel', throttledWheel, { passive: false });
    
    function throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }
    
    startProgress();

    window.switchLanguage = async (newLang) => {
        try {
            const response = await fetch('/api/switch-language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ language: newLang })
            });
            
            if (response.ok) {
                const reloadPrompt = document.querySelector('.reload-prompt');
                reloadPrompt.style.display = 'flex';
                setTimeout(() => {
                    reloadPrompt.classList.add('show');
                }, 10);
            }
        } catch (error) {
            console.error('Error switching language:', error);
        }
    };
}); 