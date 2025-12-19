// 1. 카드 리스트 검색 함수
async function searchCards() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim();
    
    if (!query) {
        alert("검색어를 입력해주세요.");
        return;
    }

    const cardListSection = document.getElementById('cardListSection');
    const cardList = document.getElementById('cardList');
    
    // 이전 결과 초기화 및 로딩 표시
    cardList.innerHTML = '<p>검색 중...</p>';
    cardListSection.classList.remove('hidden');
    document.getElementById('priceResultSection').classList.add('hidden');

    try {
        const response = await fetch(`/api/search?name=${encodeURIComponent(query)}`);
        const cards = await response.json();

        cardList.innerHTML = '';

        if (!cards || cards.length === 0) {
            cardList.innerHTML = '<p>검색 결과가 없습니다.</p>';
            return;
        }

        cards.forEach(card => {
            const cardDiv = document.createElement('div');
            cardDiv.className = 'card-item';
            cardDiv.innerHTML = `
                <h4>${card.name}</h4>
                <p style="font-size: 0.8em; color: gray;">${card.series} | ${card.number}</p>
                <button onclick="getPrices('${card.name}', '${card.series}', '${card.number}')" 
                        style="background-color: #ff4757; color: white; padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;">
                    시세 보기
                </button>
            `;
            cardList.appendChild(cardDiv);
        });
    } catch (error) {
        console.error("검색 실패:", error);
        cardList.innerHTML = '<p>서버 통신 오류가 발생했습니다.</p>';
    }
}

// 2. 이베이 시세 조회 함수
async function getPrices(name, series, number) {
    const priceSection = document.getElementById('priceResultSection');
    const tableBody = document.getElementById('priceTableBody');
    const loading = document.getElementById('loading');

    priceSection.classList.remove('hidden');
    loading.classList.remove('hidden');
    tableBody.innerHTML = ''; // 테이블 초기화

    try {
        const response = await fetch('/api/price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, series, number })
        });

        const prices = await response.json();
        loading.classList.add('hidden');

        if (!prices || prices.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="3" style="text-align:center;">최근 판매 내역이 없습니다.</td></tr>';
            return;
        }

        prices.forEach(item => {
            const row = `
                <tr>
                    <td><small>${item.title}</small></td>
                    <td><strong>${item.price} ${item.currency}</strong></td>
                    <td>${item.sold_date}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });
    } catch (error) {
        console.error("시세 조회 실패:", error);
        loading.classList.add('hidden');
        tableBody.innerHTML = '<tr><td colspan="3">데이터를 가져오는 중 오류가 발생했습니다.</td></tr>';
    }
}