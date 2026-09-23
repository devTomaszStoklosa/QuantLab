# QuantLab — dokumentacja produktowa

## 1. Czym jest QuantLab

QuantLab to platforma do prowadzenia systematycznych badań inwestycyjnych: od pomysłu na strategię, przez dane i sygnał, backtest z realnymi kosztami transakcyjnymi, walidację poza próbą, analizę ryzyka w różnych warunkach rynkowych, aż po udokumentowany wniosek.

Platforma nie dostarcza jednej gotowej strategii do handlu. Dostarcza rzetelny proces, którym można przetestować dowolną liczbę hipotez inwestycyjnych i uzyskać wiarygodną odpowiedź na pytanie, czy dana hipoteza się broni.

## 2. Jaki problem rozwiązuje

Większość nieformalnego testowania strategii inwestycyjnych pomija dyscyplinę, która decyduje o wiarygodności wyniku: testuje się na tych samych danych, na których dobrano parametry; pomija się koszty transakcyjne; nie sprawdza się zachowania strategii w różnych warunkach rynkowych; kryterium sukcesu ustala się po zobaczeniu wyniku, a nie przed. Efekt to fałszywa pewność — strategia, która „działa" na papierze, a traci pieniądze na żywym rynku, bo wynik był w rzeczywistości dopasowaniem do szumu, nie prawdziwą prawidłowością.

QuantLab wymusza brakującą dyscyplinę na każdym etapie: hipoteza jest rejestrowana i śledzona formalnie; sygnał jest testowany osobno od reszty procesu; backtest zawsze uwzględnia koszty; wynik musi przejść walidację poza próbą, zanim zostanie uznany za potwierdzony; a kryterium sukcesu i zakres danych do ostatecznego sprawdzenia są zamrażane, zanim ktokolwiek na nie spojrzy.

## 3. Dla kogo jest

- **Badacze ilościowi i analitycy**, którzy potrzebują powtarzalnego, możliwego do prześledzenia procesu badawczego, a nie jednorazowego skryptu.
- **Traderzy systematyczni**, którzy chcą rzetelnie przetestować hipotezę inwestycyjną, zanim zaryzykują realny kapitał.
- **Zespoły badawcze**, w których wynik musi być możliwy do zweryfikowania przez kogoś innego niż autor — pełny ślad metodologii i decyzji, nie tylko końcowa liczba.

## 4. Filozofia produktu

Produktem nie jest pojedyncza, dobrze działająca strategia — produktem jest proces, którym dochodzi się do wiarygodnej odpowiedzi. Z tego wynika wprost: hipoteza odrzucona po rzetelnym przetestowaniu jest tak samo wartościowym wynikiem badania, jak hipoteza potwierdzona. Obie kończą się tym samym — udokumentowanym wnioskiem, który zapobiega ponownemu sprawdzaniu tego samego pomysłu za rok, tym samym nakładem czasu.

Dwie zasady wynikają z tego wprost dla codziennego korzystania z platformy:

- Wynik „nie działa" nie jest porażką badania. Porażką jest brak dokumentacji, dlaczego nie zadziałało.
- Hipoteza nie staje się „potwierdzona" przez sam dobry wynik na danych treningowych. Potwierdza ją dopiero przejście walidacji poza próbą.

## 5. Funkcje produktu

### 5.1 Rejestr hipotez

**Po co:** formalizuje cykl życia każdego pomysłu badawczego — od zaproponowanej, przez testowaną, do potwierdzonej, odrzuconej albo niejednoznacznej — i pilnuje reguły, że nie da się oznaczyć hipotezy jako potwierdzonej bez przejścia pełnej walidacji.

**Jak korzystać dobrze:** rejestruj hipotezę, zanim zaczniesz patrzeć na dane. Sama treść hipotezy — co ma działać i dlaczego — powinna powstać przed pierwszym uruchomieniem czegokolwiek na danych, nie po.

### 5.2 Dane rynkowe i uniwersum instrumentów

**Po co:** dostarcza spójne, wiarygodne dane historyczne i jawnie definiuje, jakie instrumenty w ogóle bierze się pod uwagę w danym badaniu, żeby wynik dało się odtworzyć i sprawdzić, co dokładnie było testowane.

**Jak korzystać dobrze:** ustal uniwersum instrumentów przed testem, nie w jego trakcie. Dobieranie instrumentów pod wynik — tak, żeby „pasowały" — jest formą przeuczenia tak samo groźną jak dobieranie parametrów pod wynik.

### 5.3 Sygnały strategii

**Po co:** przekłada hipotezę inwestycyjną na konkretną, testowalną regułę decyzyjną (kiedy zająć długą, krótką, a kiedy żadną pozycję) w izolacji od reszty procesu, tak żeby dało się ocenić samą logikę strategii niezależnie od kosztów czy zarządzania ryzykiem.

**Jak korzystać dobrze:** trzymaj logikę sygnału na tyle prostą i jawną, żeby dało się dla niej podać uzasadnienie ekonomiczne — dlaczego rynek miałby dawać taki efekt — zanim zacznie się sprawdzać, czy działa statystycznie.

### 5.4 Silnik backtestu

**Po co:** symuluje, jak strategia zachowywałaby się historycznie, zamieniając sygnały w portfel i wynik w czasie, żeby ocenić hipotezę na podstawie zachowania w przeszłości, a nie intuicji.

**Jak korzystać dobrze:** traktuj pierwszy wynik backtestu jako punkt wyjścia do dalszej weryfikacji, nie jako odpowiedź ostateczną. Dobry wynik na jednym przebiegu to za mało, żeby zaufać strategii.

### 5.5 Modele kosztów transakcyjnych

**Po co:** pokazuje wprost, ile z wyniku strategii „zjadają" koszty realnego handlu — spread, prowizja, poślizg cenowy — przez porównanie wariantu uproszczonego z wariantem realistycznym.

**Jak korzystać dobrze:** nigdy nie oceniaj strategii wyłącznie na wersji bez kosztów. Jeśli wynik znika po dodaniu realistycznych kosztów, strategia nie nadaje się do dalszej pracy, niezależnie od tego, jak dobrze wyglądała wcześniej.

### 5.6 Walidacja poza próbą

**Po co:** to główna linia obrony przed przeuczeniem — sprawdza, czy wynik utrzymuje się na danych, których strategia „nie widziała" w trakcie projektowania, oraz czy nie jest przypadkowym trafieniem.

**Jak korzystać dobrze:** zamroź zakres danych do ostatecznego sprawdzenia i kryterium sukcesu, zanim zobaczysz na nich wynik — i sprawdź je dokładnie raz. Wielokrotne sprawdzanie tego samego zbioru i poprawianie strategii między próbami niszczy sens całego zabiegu.

### 5.7 Analiza ryzyka i reżimów rynkowych

**Po co:** pokazuje, czy dobry wynik „średni" nie ukrywa fatalnego zachowania akurat w warunkach, które najbardziej się liczą — np. przy wysokiej zmienności albo gwałtownej bessie.

**Jak korzystać dobrze:** zawsze sprawdzaj wynik osobno dla różnych warunków rynkowych, nie tylko łącznie za cały okres. Strategia, która traci najwięcej właśnie wtedy, gdy strata najbardziej boli, ma inny profil ryzyka, niż sugeruje sama średnia.

### 5.8 Atrybucja transakcji

**Po co:** rozkłada wynik na pojedyncze transakcje i pozwala pociąć go według warunków rynkowych, okresu utrzymania pozycji czy miesiąca, żeby zrozumieć źródło zysku lub straty, nie tylko końcową liczbę.

**Jak korzystać dobrze:** szukaj, czy wynik pochodzi z szerokiej, powtarzalnej przewagi, czy z garstki nietypowych transakcji. To drugie jest sygnałem ostrzegawczym, nawet gdy suma wygląda dobrze.

### 5.9 Raport końcowy

**Po co:** zbiera metryki, wykresy i wnioski badania w jednej, czytelnej formie, gotowej do przeglądu i decyzji, bez konieczności odtwarzania wyniku samodzielnie.

**Jak korzystać dobrze:** czytaj raport razem z metodologią, która go poprzedza — jaka hipoteza, jaki zakres danych do ostatecznego sprawdzenia, jakie koszty. Sama liczba bez kontekstu, w którym powstała, niewiele mówi o tym, ile jej ufać.

### 5.10 Dziennik badawczy

**Po co:** trwały, chronologiczny zapis każdej przetestowanej hipotezy razem z metodologią i wnioskiem, niezależnie od wyniku — pamięć instytucjonalna całego procesu badawczego.

**Jak korzystać dobrze:** zapisuj wpis od razu po zakończeniu badania, także — zwłaszcza — gdy hipoteza upadła. To zapobiega ponownemu wydawaniu czasu na sprawdzenie tego samego pomysłu za rok i buduje mapę tego, co już wiadomo.

## 6. Jak korzystać z produktu, żeby uzyskać najlepszy efekt

1. Sformułuj hipotezę pisemnie, zanim zobaczysz dane — co ma działać i dlaczego, w kategoriach ekonomicznych, nie tylko statystycznych.
2. Ustal z góry uniwersum instrumentów, zakres dat i kryterium sukcesu. Zamroź zakres danych do ostatecznego sprawdzenia, zanim go zobaczysz.
3. Zbuduj sygnał i sprawdź go w izolacji, zanim połączysz go z resztą procesu.
4. Uruchom backtest z realistycznymi kosztami transakcyjnymi, nie tylko w wariancie uproszczonym.
5. Zwaliduj wynik poza próbą, zanim padnie jakakolwiek deklaracja sukcesu.
6. Sprawdź ostateczny wynik na zamrożonym zakresie danych dokładnie raz. Nie poprawiaj strategii i nie sprawdzaj go ponownie.
7. Przeanalizuj wynik w różnych warunkach rynkowych i na poziomie pojedynczych transakcji, nie tylko jako jedną liczbę zbiorczą.
8. Zapisz wniosek w dzienniku badawczym niezależnie od wyniku. Potwierdzenie i odrzucenie dokumentuj z tą samą starannością.
9. Nie zmieniaj kryterium sukcesu ani parametrów po zobaczeniu wyniku na zamrożonych danych — to unieważnia całą walidację, którą się właśnie przeprowadziło.

## 7. Czego produkt nie robi

- Nie udziela porad inwestycyjnych. Opisuje historyczne zachowanie strategii i ryzyko — nie mówi „kup", „sprzedaj" ani „zwiększ pozycję".
- Nie wykonuje transakcji i nie zarządza realnym kapitałem. To narzędzie badawcze, nie system egzekucji.
- Nie gwarantuje przyszłych wyników. Wynik z danych historycznych, nawet rzetelnie zwalidowany, opisuje przeszłość — nie obiecuje przyszłości.

## 8. Kierunek rozwoju

Sam proces badawczy — nie pojedyncza strategia czy klasa aktywów — jest stałym elementem produktu. Metodologia jest zaprojektowana tak, żeby rozszerzać się na kolejne rodziny hipotez inwestycyjnych, inne klasy aktywów i bardziej zaawansowane techniki walidacji, bez zmiany samego procesu, przez który każda z nich przechodzi.
