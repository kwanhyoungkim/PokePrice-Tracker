cat > static/js/main.js << 'EOF'
// 1. 카드 리스트 검색 함수
async function searchCards() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim();
    
    if (!query) {
        alert("검색하실 포켓몬 이름을 입력해주세요!");
        return;
    }

    const cardListSection = document.getElementById('cardListSection');
    const cardList = document.getElementById('cardList');
    const priceSection = document.getElementById('priceResultSection');
    
    // 초기화 및 로딩 표시
    cardList.innerHTML = '<p style="text-align:center; width:100%; padding: 40px;">🔍 데이터를 찾는 중입니다...</p>';
    cardListSection.classList.remove('hidden');
    priceSection.classList.add('hidden'); 

    try {
        // 서버 API 호출
        const response = await fetch(`/api/search?name=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error("서버 응답 오류");
        
        const cards = await response.json();
        cardList.innerHTML = '';

        if (!cards || cards.length === 0) {
            cardList.innerHTML = '<p style="text-align:center; width:100%; padding: 40px;">해당하는 카드가 DB에 없습니다.</p>';
            return;
        }

        // 결과 카드 렌더링
        cards.forEach(card => {
            // 작은따옴표(') 이스케이프 처리
            const escapedName = card.name.replace(/'/g, "\\'");
            const escapedSeries = card.series.replace(/'/g, "\\'");
            
            const cardDiv = document.createElement('div');
            cardDiv.className = 'card-item';
            
            // 이미지 HTML 생성
            const imageHTML = card.image_url 
                ? `<div class="card-image-container">
                     <img src="${card.image_url}" 
                          alt="${card.name}" 
                          class="card-image"
                          onerror="this.parentElement.innerHTML='<div class=\\'card-image-placeholder\\'>🎴</div>'">
                   </div>`
                : `<div class="card-image-container">
                     <div class="card-image-placeholder">🎴</div>
                   </div>`;
            
            cardDiv.innerHTML = `
                ${imageHTML}
                <h4>${card.name}</h4>
                <div class="card-info">
                    <p class="card-set">${card.series}</p>
                    <p class="card-number">#${card.number}</p>
                </div>
                <button class="view-price-btn" 
                        onclick="getPrices('${escapedName}', '${escapedSeries}', '${card.number}')">
                    💰 실시간 시세 보기
                </button>
            `;
            cardList.appendChild(cardDiv);
        });
    } catch (error) {
        console.error("검색 에러:", error);
        cardList.innerHTML = '<p style="text-align:center; width:100%; padding: 40px; color: #e74c3c;">❌ 서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.</p>';
    }
}

// 2. 이베이 시세 조회 함수
async function getPrices(name, series, number) {
    console.log("시세 조회 요청 데이터:", { name, series, number });

    const priceSection = document.getElementById('priceResultSection');
    const tableBody = document.getElementById('priceTableBody');
    const loading = document.getElementById('loading');

    // UI 상태 설정
    priceSection.classList.remove('hidden');
    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    
    // 화면 하단 시세창으로 스무스하게 이동
    priceSection.scrollIntoView({ behavior: 'smooth' });

    try {
        const response = await fetch('/api/price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, series, number })
        });

        if (!response.ok) throw new Error("시세 데이터를 가져오는데 실패했습니다.");

        const prices = await response.json();
        loading.classList.add('hidden');

        if (!prices || prices.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:gray; padding: 20px;">최근 판매 내역을 찾을 수 없습니다. (eBay 데이터 없음)</td></tr>';
            return;
        }

        // 시세 데이터 테이블 추가
        prices.forEach(item => {
            const row = `
                <tr>
                    <td><div style="font-size:0.85rem; color:#444; line-height:1.4;">${item.title}</div></td>
                    <td><b style="color:#2f3542; white-space: nowrap;">${item.price} ${item.currency}</b></td>
                    <td style="color:#747d8c; font-size:0.85rem; white-space: nowrap;">${item.sold_date}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });
    } catch (error) {
        console.error("시세조회 에러:", error);
        loading.classList.add('hidden');
        tableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:red; padding: 20px;">❌ 서버 통신 중 오류가 발생했습니다.</td></tr>';
    }
}
EOF