"use client"; // browser component, makes it safe for reading localstorage

import { Provider } from "react-redux";
import AuthInitializer from "@/components/AuthInitializer/page";

import { store } from "@/store/store";

// Small client component, that runs once and copies stored tokens back into redux state (migrated to actual component file)
// function AuthInitializer({children}) {
//     const dispatch = useDispatch();

//     useEffect(() => {
//         dispatch(restoreAuth());
//     }, [dispatch]);

//     return children;
// }

export default function Providers({children}){
    return (
        <Provider store={store}>
            <AuthInitializer>
                {children}
            </AuthInitializer>
        </Provider>
    );
}