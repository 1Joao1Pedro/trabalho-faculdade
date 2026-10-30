<?php

use Illuminate\Support\Facades\Route;

// Laravel entrega apenas a interface Blade. Toda regra e dado ficam na API Python.
Route::view('/{page?}', 'welcome')
    ->where('page', 'cadastro|login|perfil|admin')
    ->name('home');
