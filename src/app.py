import streamlit as sl
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(
   page_title="CalcMate",
   page_icon="🔢",
   layout="wide",
   initial_sidebar_state="expanded",
)

page = sl.sidebar.radio("Pages:", ["Home", "Introduction to Limits", "One-Sided Limits", "Derivatives", "Reference"])

def PlotGraph(x, y, xlabel="x", ylabel="f(x)", title="Graph of f(x)"):
    fig, axes = plt.subplots()
    axes.plot(x, y)
    axes.set_label(title)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)

    sl.pyplot(fig)

if page == "Home":
    sl.title("CalcMate - Home")
    sl.text("Welcome to CalcMate, an app all about Calculus! Stuck on something in class? Need some more examples? You've come to the right place! CalcMate is a simple and accessible online Calculus textbook designed to explain complex Calculus topics in easy to understand ways.")
    sl.header("Who is CalcMate for?")
    sl.text("CalcMate is designed for high school students who would like to get a better grasp on certain calculus topics, refresh their memory on earlier content, or prep for finals. Although high school students were the initial target audience, CalcMate can be useful to anyone looking to learn more about calculus.")
elif page == "Introduction to Limits":
    sl.title("CalcMate - Introduction to Limits")
    sl.text("\"What the heck is a limit?\"\nThat's probably what every Calculus student has said to themselves after being introduced to the topic. Don't let the ambiguous name intimidate you though, limits are actually quite intuitive and easy to learn. Let's get into it!")
    sl.header("The Limit")
    sl.text("Whem thinking about what a limit actually is, the game of Blackjack comes to mind. For those unfamiliar, in the game, the player is dealt cards, these cards' value is added up, and the sum of the players cannot go over 21. The goal is to get as close to 21 as possible without going past. Sometime the player will get 21 exactly, sometimes the player will be really close with a 19 or 20.")
    sl.text("Now you're probably wondering, what does this have to do with Calculus? Well, the limit of a function is the value as the function approaches (but doesn't necessarily reach) a number.")
    sl.header("Limit Notation")
    sl.text("Now, let's look at the notation for writing limits.")
    sl.latex(r"\lim_{x \to a} f(x)")
    sl.text("Let's break it down. What this is really saying is: \"The limit of the function f(x) when x approaches a\". 'a' is a placeholder for a number. In easier terms, it's asking what f(x) equals when x gets really close to the number 'a'. Let's try an example.")
    sl.latex(r"f(x) = x^2")
    sl.latex(r"\lim_{x \to 2} f(x) = ?")
    sl.text("To solve this limit, lets try plugging in numbers really close to (but not quite) 2.")

    tb = pd.DataFrame([
        {"x" : "1.9", "f(x)" : "3.61"},
        {"x" : "1.99", "f(x)" : "3.9601"},
        {"x" : "1.999", "f(x)" : "3.996001"},
        {"x" : "2.001", "f(x)" : "4.004001"},
        {"x" : "2.01", "f(x)" : "4.0401"},
        {"x" : "2.1", "f(x)" : "4.41"},
    ])

    sl.data_editor(tb, hide_index=True, disabled=True)
    sl.text("Do you see the pattern? The closer x gets to 2, f(x) gets closer to 4. If you think about it, this makes sense becasue 2 squared is 4. Therefore:")
    sl.latex(r"\lim_{x \to 2} f(x) = 4")
    sl.text("Good job! Now it's your turn, try some of these practice problems.")
    sl.header("Practice Problems")
    sl.latex(r"f(x) = 4x")
    sl.latex(r"\lim_{x \to 3} f(x) = ?")
    with sl.expander("Answer"):
        sl.text("12")
    with sl.expander("Explanation"):
        sl.text("For this limit, we can simply plug 3 into the original function. f(3) is equal to 12, so the limit of f(x) approaching 3 is 12.")
    
    sl.latex(r"g(x) = 2x^2 + 3x - 2")
    sl.latex(r"\lim_{x \to 1} g(x) = ?")
    with sl.expander("Answer"):
        sl.text("3")
    with sl.expander("Explanation"):
        sl.text("For this limit, we can also plug 1 into the original function. g(1) is equal to 3, so the limit of g(x) approaching 1 is 3.")

    sl.latex(r"h(x) = \frac{x}{x-5}")
    sl.latex(r"\lim_{x \to 5} h(x) = ?")
    with sl.expander("Answer"):
        sl.text("The limit does not exist")
    with sl.expander("Explanation"):
        sl.text("This limit is a bit trickier. If you try plugging in 5, you get 5/0, and dividing by zero isn't possible in math, so we'll have to work a bit harder. If you look at the graph of the function, you will see something interesting.")
        
        x1 = np.linspace(-10, 20, 300)
        y1 = x1/(x1-5)

        PlotGraph(x1, y1, ylabel="h(x)", title="Graph of h(x)")

        sl.text("You can see that there is actually a vertical asymptote at x = 5. If we looked at numbers increasing to 5, h(x) is decreasing towards negative infinity. On the other hand, x-values slightly larger than 5 that decrease towards 5 result in h(x) increasing to infinity. Since these values don't meet at the same value, the limit does not exist.")

elif page == "One-Sided Limits":
    sl.title("CalcMate - One-Sided Limits")
    sl.text("On the last practice problem of the previous page, we were introduced to an interesting concept: Limits that don't exist. In this chapter we will explain deeper what it means for a limit to exist.")
    sl.header("What is a discontinuity?")
    sl.text("A discontinuity is essentially any point on a graph where there is a break of any sort in the line. Let's go over and see some examples of each type.")

    with sl.expander("Vertical Asymtotes"):
        sl.latex(r"h(x) = \frac{x}{x-5}")
        x = np.linspace(-10, 20, 300)
        y = x/(x-5)
        PlotGraph(x, y, ylabel="h(x)", title="Graph of h(x)")
        sl.text("Here's the graph from the last practice problem. Here we can see a vertical asymtote, a discontinuity where the function's value approaches positive or negative infinity at a certain x-value.")

    with sl.expander("Hole"):
        sl.latex(r"f(x) = \frac{x^2}{x}")
        x = np.linspace(-10, 10, 200)
        y = x
        PlotGraph(x,y)
        sl.text("This graph doesn't appear to have a discontinuity, but if you consider the function, you might see that there is a discontinuity at x = 0. If you try plugging 0 in, you will get 0/0, which is undefined. This is because a hole is a specific type of discontinuity known as a removable discontinuity. You can simplify the function to f(x) = x. Since the discontinuity is removable, the limit can still exist.")

    with sl.expander("Jump Discontinuity"):
        sl.latex(r"g(x) = \begin{cases} x, & \text{if } x > 0; \\ 5, & \text{if } x <= 0; \end{cases}")

        x = np.linspace(-10, 10, 200)
        y = np.zeros_like(x)
        y[x > 0] = x[x > 0]
        y[x <= 0] = 5

        PlotGraph(x,y, ylabel="g(x)", title="Graph of g(x)")

        sl.text("In a jump discontinity, the function approaches one value from the right, and a seperate value from the left. This causes a visible 'jump' in the graph.")

    sl.header("One-Sided Limits")
    sl.text("As you have seen above, it is possible for a function to approach different values depending on if we follow the line from the left or the right. How can we evaluate these? Well, with one sided limits. One sided limits specify whether to look for the limit from the left or from the right.")
    sl.latex(r"\lim_{x \to a^-} f(x)")
    sl.latex(r"\lim_{x \to a^+} f(x)")
    sl.text("This is the notation for left and right hand limits respectively.")
    sl.header("Continuity")
    sl.text("A function is considered continuous at a given point if both the left and right hand limits at that point exist and are equal to each other. If they do not, or a hole exists there, then the function is considered 'discontinuous'.")
elif page == "Derivatives":
    sl.title("CalcMate - Derivatives")
    sl.header("What is a Derivative?")
    sl.text("Most math you have learned up to calculus focuses on simple functions with an X input and a Y output. If you think of this kind of function as telling you the position of a car at a given time, then the derivative of that function would be another function that tells you the velocity of the car at a given time. Let's dive deeper.")
    sl.header("Definition of a Derivative")
    sl.text("The formula to find the slope between two points on a line is:")
    sl.latex(r"\frac{f(x_1) - f(x_2)}{x_1 - x_2}")
    sl.text("This gives us the slope, or the average rate of change between two points. The idea behind the derivative is that if the distance between the two points gets super close to zero but not actually zero (sound familiar?), we will get the slope of a line tangent to the graph at that point. This slope is the instantaneous rate of change! With that in mind, we can come up with the definition of a derivative as:")
    sl.latex(r"\lim_{\Delta x \to 0} \frac{f(x + \Delta x) - f(x)}{\Delta x}")
    sl.text("With Δx representing the difference between the two points.")


    sl.header("Derivative Rules")
    sl.text("There are several rules to help derive a function faster. Here are some of the most common.")
    sl.latex(r"\text{Constant Rule: } \frac{d}{dx}C = 0")
    sl.latex(r"\text{Constant Multiplication Rule: } \frac{d}{dx}[Cf(x)] = Cf^\prime(x)")
    sl.latex(r"\text{Sum Rule: } \frac{d}{dx}[f(x) + g(x)] = f^\prime(x) + g^\prime(x)")
    sl.latex(r"\text{Difference Rule: } \frac{d}{dx}[f(x) - g(x)] = f^\prime(x) - g^\prime(x)")
    sl.latex(r"\text{Product Rule: } \frac{d}{dx}[f(x) \cdot g(x)] = f^\prime(x) \cdot g(x) + g^\prime(x) \cdot f(x)")
    sl.latex(r"\text{Quotient Rule: } \frac{d}{dx}[\frac{f(x)}{g(x)}] = \frac{g(x) \cdot f^\prime(x) - f(x) \cdot g^\prime(x)}{g(x)^2}")
    sl.latex(r"\text{Constant Rule: } \frac{d}{dx}x^n = nx^{n-1}")
    sl.latex(r"\text{Chain Rule: } \frac{d}{dx}f(g(x)) = f'(g(x)) \cdot g'(x)")
    sl.latex(r"\text{Natural Log Rule: } \frac{d}{dx}\ln(u) = \frac{u^\prime}{u}")
    sl.latex(r"\text{Log Rule: } \frac{d}{dx}\log_{a}(u) = \frac{u^\prime}{\ln{a} \cdot u}")
    sl.latex(r"\text{Exponent Rule: } \frac{d}{dx}a^u = a^u \cdot \ln{a} \cdot u^\prime")
    sl.latex(r"\text{Natural Exponent Rule: } \frac{d}{dx}e^u = e^u \cdot u^\prime")

    sl.header("Trig Derivatives")
    sl.latex(r"\frac{d}{dx}\sin(x) = \cos(x)")
    sl.latex(r"\frac{d}{dx}\cos(x) = -\sin(x)")
    sl.latex(r"\frac{d}{dx}\tan(x) = \sec^2(x)")
    sl.latex(r"\frac{d}{dx}\csc(x) = -\csc(x) \cdot \cot(x)")
    sl.latex(r"\frac{d}{dx}\sec(x) = \sec(x) \cdot \tan(x)")
    sl.latex(r"\frac{d}{dx}\cot(x) = -\csc^2(x)")

    sl.header("Practice Problems")
    sl.latex(r"\frac{d}{dx}x^2 + 25x")
    with sl.expander("Answer"):
        sl.latex(r"2x + 25")

    sl.latex(r"\frac{d}{dx}x^5 + 2x^4 - 3x^3 - x^2 + 25x + 67")
    with sl.expander("Answer"):
        sl.latex(r"5x^4 + 8x^3 - 9x^2 - 2x + 25")

    sl.latex(r"\frac{d}{dx}\sin{x^2}")
    with sl.expander("Answer"):
        sl.latex(r"2x \cdot \cos{x^2}")
    
    sl.latex(r"\frac{d}{dx}\frac{x}{x + 1}")
    with sl.expander("Answer"):
        sl.latex(r"\frac{1}{(x+1)^2}")

    sl.latex(r"\frac{d}{dx}\sqrt{x}")
    with sl.expander("Answer"):
        sl.latex(r"\frac{1}{2\sqrt{x}}")
    
    sl.latex(r"\frac{d}{dx}e^{x^3}")
    with sl.expander("Answer"):
        sl.latex(r"e^{x^3} \cdot 3x^2")

    sl.latex(r"\frac{d}{dx}\sin(\tan(x^2))")
    with sl.expander("Answer"):
        sl.latex(r"2x \cdot \cos(\tan(x^2)) \cdot \sec^2(x^2)")

    sl.latex(r"\frac{d}{dx}\sin(x) \cdot \cos(x)")
    with sl.expander("Answer"):
        sl.latex(r"\cos^2(x) - sin^2(x)")

elif page == "Reference":
    with sl.expander("Derivative Rules"):
        sl.latex(r"\text{Constant Rule: } \frac{d}{dx}C = 0")
        sl.latex(r"\text{Constant Multiplication Rule: } \frac{d}{dx}[Cf(x)] = Cf^\prime(x)")
        sl.latex(r"\text{Sum Rule: } \frac{d}{dx}[f(x) + g(x)] = f^\prime(x) + g^\prime(x)")
        sl.latex(r"\text{Difference Rule: } \frac{d}{dx}[f(x) - g(x)] = f^\prime(x) - g^\prime(x)")
        sl.latex(r"\text{Product Rule: } \frac{d}{dx}[f(x) \cdot g(x)] = f^\prime(x) \cdot g(x) + g^\prime(x) \cdot f(x)")
        sl.latex(r"\text{Quotient Rule: } \frac{d}{dx}[\frac{f(x)}{g(x)}] = \frac{g(x) \cdot f^\prime(x) - f(x) \cdot g^\prime(x)}{g(x)^2}")
        sl.latex(r"\text{Constant Rule: } \frac{d}{dx}x^n = nx^{n-1}")
        sl.latex(r"\text{Chain Rule: } \frac{d}{dx}f(g(x)) = f'(g(x)) \cdot g'(x)")
        sl.latex(r"\text{Chain Rule: } \frac{d}{dx}f(g(x)) = f'(g(x)) \cdot g'(x)")
        sl.latex(r"\text{Natural Log Rule: } \frac{d}{dx}\ln(u) = \frac{u^\prime}{u}")
        sl.latex(r"\text{Log Rule: } \frac{d}{dx}\log_{a}(u) = \frac{u^\prime}{\ln{a} \cdot u}")
        sl.latex(r"\text{Exponent Rule: } \frac{d}{dx}a^u = a^u \cdot \ln{a} \cdot u^\prime")
        sl.latex(r"\text{Natural Exponent Rule: } \frac{d}{dx}e^u = e^u \cdot u^\prime")

    with sl.expander("Trig Derivative Rules"):
        sl.latex(r"\frac{d}{dx}\sin(x) = \cos(x)")
        sl.latex(r"\frac{d}{dx}\cos(x) = -\sin(x)")
        sl.latex(r"\frac{d}{dx}\tan(x) = \sec^2(x)")
        sl.latex(r"\frac{d}{dx}\csc(x) = -\csc(x) \cdot \cot(x)")
        sl.latex(r"\frac{d}{dx}\sec(x) = \sec(x) \cdot \tan(x)")
        sl.latex(r"\frac{d}{dx}\cot(x) = -\csc^2(x)")

    with sl.expander("Inverse Trig Derivative Rules"):
        sl.latex(r"\frac{d}{dx}\sin^{-1}(x) = \frac{1}{\sqrt{1 - x^2}}")
        sl.latex(r"\frac{d}{dx}\cos^{-1}(x) = -\frac{1}{\sqrt{1 - x^2}}")
        sl.latex(r"\frac{d}{dx}\tan^{-1}(x) = \frac{1}{1 + x^2}")
        sl.latex(r"\frac{d}{dx}\csc^{-1}(x) = -\frac{1}{|x|\sqrt{x^2 - 1}}")
        sl.latex(r"\frac{d}{dx}\sec^{-1}(x) = \frac{1}{|x|\sqrt{x^2 - 1}}")
        sl.latex(r"\frac{d}{dx}\cot^{-1}(x) = -\frac{1}{1 + x^2}")

    with sl.expander("L'Hôpital's Rule"):
        sl.latex(r"\text{if } \lim_{x \to a}\frac{f(x)}{g(x)} \text{ is indereminate (0/0), then } \lim_{x \to a}\frac{f(x)}{g(x)} = \lim_{x \to a}\frac{f^\prime(x)}{g^\prime(x)}")
